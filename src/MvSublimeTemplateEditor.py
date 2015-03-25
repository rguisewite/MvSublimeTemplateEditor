import sublime, sublime_plugin
import json
import os.path

try:
	import urllib.request as urllib2
except ImportError:
	import urllib2

import urllib.parse
import re
import threading

import os, random, string
import subprocess
from subprocess import Popen, PIPE, STDOUT

# Check to see if we're in Sublime Text 3
ST3 				= int(sublime.version()) >= 3000
master_password 	= None
openssl_enabled		= True

#
# Pages / Templates Quick Panel Load
#

class MvSublimeTemplateEditorGetSitesCommand( sublime_plugin.WindowCommand ):
	def run( self, type = 'pages' ):
		global openssl_enabled

		self.type 		= type
		self.settings 	= sublime.load_settings( 'MvSublimeTemplateEditor.sublime-settings' )

		if self.settings.has( 'disable_master_password' ):
			openssl_enabled	= not self.settings.get( 'disable_master_password' )

		self.load_sites()

		if openssl_enabled and not self.settings.has( 'password_verification' ):
			sublime.error_message( 'Master password not set. Close this dialog and enter a master password' )
			return self.set_master_password()

	def load_sites( self ):
		global master_password, openssl_enabled

		self.sites = []

		for site in self.settings.get( 'sites', [] ):
			self.sites.append( site[ 'name' ] )

		self.sites.append( 'Add Store' )

		if openssl_enabled and master_password == None:
			return self.prompt_master_pass()

		self.show_sites()

	def show_sites( self ):
		sublime.set_timeout( lambda: self.window.show_quick_panel( self.sites, lambda index: self.site_callback( self.sites, index ) ) )

	def prompt_master_pass( self ):
		PasswordInputPanel( 'Enter Master Password', self.prompt_master_pass_callback )

	def prompt_master_pass_callback( self, password ):
		global master_password
		try:
			success, data, error_message = crypto( password, self.settings.get( 'password_verification' ), '-d' )

			if not success:
				sublime.error_message( error_message )
				return self.prompt_master_pass()
			elif data.decode( encoding='UTF-8' ) != 'VERIFIED':
				sublime.error_message( 'Invalid master password' )
				return self.prompt_master_pass()

		except KeyError:
			sublime.error_message( 'Master password not set. Close this dialog and enter a master password' )
			return self.set_master_password()

		master_password = password
		self.show_sites()

	def site_callback( self, sites, index ):
		if index == -1:
			return

		if sites[ index ] == 'Add Store':
			return self.add_store()

		settings 	= None
		site 		= sites[ index ]

		try:
			for site_settings in self.settings.get( 'sites', [] ):
				if site_settings[ 'name' ] == site:
					settings = site_settings
					break
		except KeyError:
			sublime.error_message( 'Site not found' )
			return
		except Exception:
			sublime.error_message( 'Invalid configuration file' )
			return

		if settings == None:
			sublime.error_message( 'Site not found' )
			return

		if self.type == 'pages':
			self.window.run_command( 'mv_sublime_template_editor_get_pages', { 'settings': settings } )
		elif self.type == 'templates':
			self.window.run_command( 'mv_sublime_template_editor_get_templates', { 'settings': settings } )

	def set_master_password( self ):
		PasswordInputPanel( 'Set Master Password', self.set_master_password_callback )

	def set_master_password_callback( self, master_pass ):
		global master_password
		success, data, error_message = crypto( master_pass, 'VERIFIED', '-e' )

		if not success:
			return sublime.error_message( error_message )

		master_password = master_pass
		self.settings.set( 'password_verification', data.decode(encoding='UTF-8') )
		sites 		= self.settings.get( 'sites' )

		for site in sites:
			success, encrypted_password, error_message = crypto( master_password, site[ 'store' ][ 'password' ], '-e' )

			if success:
				site[ 'store' ][ 'password_encrypted' ] 	= True
				site[ 'store' ][ 'password' ] 				= encrypted_password.decode( encoding='UTF-8' )

		self.settings.set( 'sites', sites )
		sublime.save_settings( 'MvSublimeTemplateEditor.sublime-settings' )

		self.show_sites()

	def add_store( self ):
		site 			= {}
		site[ 'store' ] = {}

		self.show_input_panel( 'Enter Store Name', '', lambda store_name: self.add_store_callback( site, store_name ), None, None )

	def add_store_callback( self, site, store_name ):
		site[ 'name' ] = store_name
		self.add_store_template_location( site )

	def add_store_template_location( self, site ):
		self.show_input_panel( 'Enter Template Export Location', '', lambda entered_text: self.add_store_template_location_callback( site, entered_text ), None, None )

	def add_store_template_location_callback( self, site, template_location = '/tmp/' ):
		site[ 'local_exported_templates' ] = template_location
		self.add_store_code( site )

	def add_store_code( self , site ):
		self.show_input_panel( 'Enter Store Code', '', lambda entered_text: self.add_store_code_callback( site, entered_text ), None, None )

	def add_store_code_callback( self, site, store_code ):
		site[ 'store' ][ 'store_code' ] = store_code
		self.add_store_jsonurl( site )

	def add_store_jsonurl( self, site ):
		self.show_input_panel( 'Enter JSON URL to Store', '', lambda entered_text: self.add_store_jsonurl_callback( site, entered_text ), None, None )

	def add_store_jsonurl_callback( self, site, json_url ):
		site[ 'store' ][ 'json_url' ] = json_url
		self.add_store_username( site )

	def add_store_username( self, site ):
		self.show_input_panel( 'Enter Username', '', lambda entered_text: self.add_store_username_callback( site, entered_text ), None, None )

	def add_store_username_callback( self, site, username ):
		site[ 'store' ][ 'username' ] = username
		self.add_store_password( site )

	def add_store_password( self, site ):
		self.show_input_panel( 'Enter Password', '', lambda entered_text: self.add_store_password_callback( site, entered_text ), None, None )

	def add_store_password_callback( self, site, password ):
		global master_password, openssl_enabled

		if openssl_enabled:
			success, data, error_message = crypto( master_password, password, '-e' )

			if not success:
				return sublime.error_message( error_message )

			password = data.decode( encoding='UTF-8' )
			site[ 'store' ][ 'password_encrypted' ] = True

		site[ 'store' ][ 'password' ] 	= password
		site[ 'store' ][ 'timeout' ]	= 15

		sites = self.settings.get( 'sites' )
		sites.append( site )
		self.settings.set( 'sites', sites )
		sublime.save_settings( 'MvSublimeTemplateEditor.sublime-settings' )

		self.load_sites()

	def show_input_panel( self, caption, initial_text, on_done, on_change = None, on_cancel = None ):
		sublime.set_timeout( lambda: self.window.show_input_panel( caption, initial_text, on_done, on_change, on_cancel ), 10 )

class MvSublimeTemplateEditorGetPagesCommand( sublime_plugin.WindowCommand ):
	def run( self, settings = None ):
		self.settings = settings

		if self.settings is None:
			return self.window.run_command( 'mv_sublime_template_editor_get_sites', { 'type': 'pages' } )

		thread = TemplateList_Load_Pages_Thread( self.settings, on_complete = self.pages_quick_panel )
		thread.start()
		ThreadProgress( thread, 'Loading pages', error_message = 'Failed loading pages' )

	def pages_quick_panel( self, pages ):
		entries = []

		for page in pages:
			entries.extend( [ '{0} - {1}' . format( page[ 'page_code' ], page[ 'page_name' ] ) ] )

		self.show_quick_panel( entries, lambda index: self.pages_callback( pages, index ) )

	def pages_callback( self, pages, index ):
		if index == -1:
			return

		# Load templates for page
		page_code = pages[ index ][ 'page_code' ]
		self.window.run_command( 'mv_sublime_template_editor_get_page', { 'settings': self.settings, 'page_code': page_code } )

	def show_quick_panel( self, entries, on_select, on_highlight = None ):
		sublime.set_timeout( lambda: self.window.show_quick_panel( entries, on_select, on_highlight = on_highlight ), 10 )

class MvSublimeTemplateEditorGetPageCommand( sublime_plugin.WindowCommand ):
	def run( self, settings = None, page_code = None ):
		self.settings 					= settings
		self.page_code 					= page_code
		self.current_view 				= self.window.active_view()
		self.selected_index				= 0
		self.template_load_initiated	= False
		settings 						= sublime.load_settings( 'MvSublimeTemplateEditor.sublime-settings' )
		self.file_args					= sublime.TRANSIENT

		if self.page_code is None:
			return

		if settings is None:
			return

		thread = TemplateList_Load_Page_Thread( page_code, self.settings, on_complete = self.templates_quick_panel )
		thread.start()
		ThreadProgress( thread, 'Loading templates', error_message = 'Failed loading templates' )

	def templates_quick_panel( self, templates ):
		entries = []

		for index, template in enumerate( templates ):
			entries.extend( [ '{0}' . format( template[ 'display' ] ) ] )

			if not self.template_load_initiated:
				self.initiate_template_download( templates, template, index )

		self.template_load_initiated = True
		self.show_quick_panel( entries, lambda index: self.select_entry( templates, index ), lambda index: self.on_highlight( templates, index ), self.selected_index )

	def select_entry( self, templates, index ):
		if index == -1:
			if self.current_view:
				self.window.focus_view( self.current_view )
			return

		self.file_args 			= 0
		self.selected_index 	= index
		
		self.goto_file( templates[ index ], self.file_args )

	def on_highlight( self, templates, index ):
		if index == -1:
			if self.current_view:
				self.window.focus_view( self.current_view )
			return

		self.selected_index = index
		self.goto_file( templates[ index ], self.file_args )

	def initiate_template_download( self, templates, template, index ):
		parameters = '&Module_Code=sublime_templateeditor&Module_Function=Template_Load_ID&ManagedTemplateVersion_ID={0}&TemporarySession=1' . format( template[ 'current_id' ] )
		json_threadpool.add_request( self.settings, parameters, lambda record: self.download_template( template, record, index ) )

	def download_template( self, template, record, index ):
		record[ 'template_name' ]	= template[ 'filename' ]
		template[ 'record' ] 		= record
		thread						= Template_Write_File( template, self.settings.get( 'local_exported_templates', '' ), lambda ignore: self.download_template_callback( template, index ) )
		thread.start()

	def download_template_callback( self, template, index ):
		if index == self.selected_index:
			self.goto_file( template, self.file_args )

	def goto_file( self, template, file_args = 0 ):
		local_directory		= self.settings.get( 'local_exported_templates', '' )

		try:
			file_name 		= '{0}' . format( template[ 'record' ][ 'template_name' ] )
		except KeyError:
			return			# File hasn't loaded yet. Don't do anything.

		local_file_path		= os.path.join( local_directory, file_name )
		view 				= self.window.open_file( local_file_path, file_args )
		view_settings 		= view.settings()
		view_settings.set( 'miva_managedtemplateversion', "true" )
		view_settings.set( 'miva_managedtemplateversion_template', template[ 'record' ] )
		view_settings.set( 'miva_settings', self.settings )
		view_settings.set( 'miva_managedtemplateversion_page_code', self.page_code )

	def show_quick_panel( self, entries, on_select, on_highlight = None, selected_index = 0 ):
		sublime.set_timeout( lambda: self.window.show_quick_panel( entries, on_select, 0, selected_index, on_highlight ), 10 )

class MvSublimeTemplateEditorGetTemplatesCommand( sublime_plugin.WindowCommand ):
	def run( self, settings = None ):
		self.settings 			= settings
		self.selected_index 	= 0
		self.file_args			= sublime.TRANSIENT
		self.current_view 		= self.window.active_view()

		if self.settings is None:
			return self.window.run_command( 'mv_sublime_template_editor_get_sites', { 'type': 'templates' } )

		thread = TemplateList_Load_All_Thread( self.settings, on_complete = self.templates_quick_panel )
		thread.start()
		ThreadProgress( thread, 'Loading templates', error_message = 'Failed loading templates' )

	def templates_quick_panel( self, templates ):
		entries = []

		for template in templates:
			entries.extend( [ 'Template file - {0}' . format( template[ 'filename' ] ) ] )

		self.show_quick_panel( entries, lambda index: self.select_entry( templates, index ), lambda index: self.on_highlight( templates, index ), self.selected_index )

	def select_entry( self, templates, index ):
		if index == -1:
			if self.current_view:
				self.window.focus_view( self.current_view )
			return

		self.file_args 			= 0
		self.selected_index 	= index

		try:
			dummy 				= templates[ index ][ 'record' ][ 'template_name' ]
		except KeyError:
			self.initiate_template_download( templates, templates[ index ], index )
			# File hasn't loaded yet. Don't do anything.

			return
		
		self.goto_file( templates[ index ], self.file_args )

	def on_highlight( self, templates, index ):
		if index == -1:
			if self.current_view:
				self.window.focus_view( self.current_view )
			return

		self.selected_index 	= index

		try:
			dummy 				= templates[ index ][ 'record' ][ 'template_name' ]
		except KeyError:
			self.initiate_template_download( templates, templates[ index ], index )
			# File hasn't loaded yet. Don't do anything.

			return

		self.goto_file( templates[ index ], self.file_args )

	def initiate_template_download( self, templates, template, index ):
		parameters = '&Module_Code=sublime_templateeditor&Module_Function=Template_Load_ID&ManagedTemplateVersion_ID={0}&TemporarySession=1' . format( template[ 'current_id' ] )
		json_threadpool.add_request( self.settings, parameters, lambda record: self.download_template( template, record, index ) )

	def download_template( self, template, record, index ):
		record[ 'template_name' ]	= template[ 'filename' ]
		template[ 'record' ] 		= record
		thread						= Template_Write_File( template, self.settings.get( 'local_exported_templates', '' ), lambda ignore: self.download_template_callback( template, index ) )
		thread.start()

	def download_template_callback( self, template, index ):
		if index == self.selected_index:
			self.goto_file( template, self.file_args )

	def goto_file( self, template, file_args = 0 ):
		local_directory		= self.settings.get( 'local_exported_templates', '' )

		try:
			file_name 		= '{0}' . format( template[ 'record' ][ 'template_name' ] )

		except KeyError:
			return			# File hasn't loaded yet. Don't do anything.

		local_file_path		= os.path.join( local_directory, file_name )
		view 				= self.window.open_file( local_file_path, file_args )
		view_settings 		= view.settings()
		view_settings.set( 'miva_managedtemplateversion', "true" )
		view_settings.set( 'miva_managedtemplateversion_template', template[ 'record' ] )
		view_settings.set( 'miva_settings', self.settings )
		view_settings.set( 'miva_managedtemplateversion_page_code', self.page_code )

	def show_quick_panel( self, entries, on_select, on_highlight = None, selected_index = 0 ):
		sublime.set_timeout( lambda: self.window.show_quick_panel( entries, on_select, 0, selected_index, on_highlight ), 10 )

#
# Template Menu
#

class MvSublimeTemplateEditorTemplateMenu( sublime_plugin.WindowCommand ):
	def run( self ):
		self.view			= self.window.active_view()
		self.view_settings	= self.view.settings()

		if not self.view_settings.has( 'miva_managedtemplateversion' ):
			return

		self.settings	= self.view_settings.get( 'miva_settings' )

		if self.settings is None:
			return

		commands		= [ 'Commit', 'Versions' ]

		if self.view_settings.has( 'miva_managedtemplateversion_page_code' ):
			commands.append( 'Templates In Page "{0}"' . format( self.view_settings.get( 'miva_managedtemplateversion_page_code' ) ) )

		sublime.set_timeout( lambda: self.window.show_quick_panel( commands, lambda index: self.command_callback( commands, index ) ) )

	def command_callback( self, commands, index ):
		if index == -1:
			return

		if commands[ index ] == 'Commit':
			self.on_save( self.view )
		elif commands[ index ] == 'Templates In Page "{0}"' . format( self.view_settings.get( 'miva_managedtemplateversion_page_code' ) ):
			self.window.run_command( 'mv_sublime_template_editor_get_page', { 'settings': self.settings, 'page_code': self.view_settings.get( 'miva_managedtemplateversion_page_code' ) } )
		elif commands[ index ] == 'Versions':
			thread = TemplateVersionList_Load_Template_Thread( self.view_settings.get( 'miva_managedtemplateversion_template' )[ 'templ_id' ], self.settings, on_complete = self.versions_quick_panel )
			thread.start()
			ThreadProgress( thread, 'Loading versions', error_message = 'Failed loading versions' )

	def on_save( self, view ):
		file_path 	= view.file_name()
		settings 	= view.settings()

		if not settings.has( 'miva_managedtemplateversion' ):
			return

		template			= settings.get( 'miva_managedtemplateversion_template' )
		source 				= view.substr( sublime.Region( 0, view.size() ) )
		thread 				= Template_Update_ID( template[ 'templ_id' ], source, self.settings, on_complete = None )
		thread.start()
		ThreadProgress( thread, 'Uploading {0}' . format( template[ 'template_name' ] ), '{0} uploaded' . format( template[ 'template_name' ] ), 'Upload of {0} failed' . format( template[ 'template_name' ] ) )

	def versions_quick_panel( self, templates ):
		entries = []

		for template in templates:
			entries.extend( [ 'Note - {0}' . format( template[ 'notes' ] ) ] )

		self.show_quick_panel( entries, lambda index: self.templates_callback( templates, index ) )

	def templates_callback( self, templates, index ):
		if index == -1:
			return

		filename 			= templates[ index ][ 'filename' ]
		current_id			= templates[ index ][ 'id' ]
		thread 				= Template_Load_ID( current_id, "{0}-{1}" . format( filename, current_id ), self.settings, on_complete = self.download_template )
		thread.start()
		ThreadProgress( thread, 'Exporting {0}' . format( filename ), '{0} exported' . format( filename ), 'Export of {0} failed' . format( filename ) )

	def download_template( self, template ):
		local_directory		= self.settings.get( 'local_exported_templates', '' )
		file_name 			= '{0}.htm' . format ( template[ 'template_name' ] )
		local_file_path		= os.path.join( local_directory, file_name )
		with open( local_file_path, 'w' ) as fh:
				fh.write( template[ 'source' ] )
		view = self.window.open_file( local_file_path )
		view_settings = view.settings()
		view_settings.set( 'miva_managedtemplateversion', "true" )
		view_settings.set( 'miva_managedtemplateversion_template', template )
		view_settings.set( 'miva_settings', self.settings )

	def show_quick_panel( self, entries, on_select, on_highlight = None ):
		sublime.set_timeout( lambda: self.window.show_quick_panel( entries, on_select, on_highlight = on_highlight ), 10 )

#
# Thread Functionality
#

class ThreadProgress():
	def __init__( self, thread, message, success_message = '', error_message = '' ):
		self.thread 			= thread
		self.message 			= message
		self.success_message 	= success_message
		self.error_message		= error_message
		self.addend 			= 1
		self.size 				= 8

		sublime.set_timeout( lambda: self.run( 0 ), 100 )

	def run( self, i ):
		if not self.thread.is_alive():
			if hasattr( self.thread, 'result' ) and not self.thread.result:
				return sublime.status_message('')

			if hasattr( self.thread, 'error' ) and self.thread.error:
				return sublime.status_message( self.error_message )

			return sublime.status_message( self.success_message )

		before 	= i % self.size
		after 	= ( self.size - 1 ) - before

		sublime.status_message( '{0} [{1}={2}]' . format( self.message, ' ' * before, ' ' * after ) )

		if not after:
			self.addend = -1

		if not before:
			self.addend = 1

		i += self.addend

		sublime.set_timeout( lambda: self.run( i ), 100 )

class TemplateList_Load_Pages_Thread( threading.Thread ):
	def __init__( self, settings, on_complete ):
		self.settings 		= settings
		self.on_complete	= on_complete
		self.error			= False
		threading.Thread.__init__( self )

	def run( self ):
		store_settings = self.settings.get( 'store' )

		print( 'Retrieving pages' )

		result, response, error = make_json_request( store_settings, 'Module', '&Count=0&Module_Code=sublime_templateeditor&Module_Function=TemplateList_Load_Pages&TemporarySession=1' )

		if not result:
			self.error = True
			return sublime.error_message( error )

		pages = response[ 'data' ][ 'data' ]

		print( 'Retrieved {0} pages' . format( len( pages ) ) )

		sublime.set_timeout( lambda: self.on_complete( pages ), 10 )

class TemplateList_Load_Page_Thread( threading.Thread ):
	def __init__( self, page_code, settings, on_complete ):
		self.page_code		= page_code
		self.settings 		= settings
		self.on_complete	= on_complete
		self.error			= False
		threading.Thread.__init__( self )

	def run( self ):
		store_settings = self.settings.get( 'store' )

		print( 'Retrieving templates' )

		result, response, error = make_json_request( store_settings, 'Module', '&Count=0&Module_Code=sublime_templateeditor&Module_Function=TemplateList_Load_Page&Page_Code={0}&TemporarySession=1' . format( urllib.parse.quote_plus( self.page_code.encode( 'utf8' ) ) ) )

		if not result:
			self.error = True
			return sublime.error_message( error )

		templates = response[ 'data' ][ 'data' ]

		print( 'Retrieved {0} templates' . format( len( templates ) ) )

		sublime.set_timeout( lambda: self.on_complete( templates ), 10 )

class TemplateList_Load_All_Thread( threading.Thread ):
	def __init__( self, settings, on_complete ):
		self.settings 		= settings
		self.on_complete	= on_complete
		self.error			= False
		threading.Thread.__init__( self )

	def run( self ):
		store_settings = self.settings.get( 'store' )

		print( 'Retrieving templates' )

		result, response, error = make_json_request( store_settings, 'Module', '&Count=0&Module_Code=sublime_templateeditor&Module_Function=TemplateList_Load_All&TemporarySession=1' )

		if not result:
			self.error = True
			return sublime.error_message( error )

		templates = response[ 'data' ][ 'data' ]

		print( 'Retrieved {0} templates' . format( len( templates ) ) )

		sublime.set_timeout( lambda: self.on_complete( templates ), 10 )

class TemplateVersionList_Load_Template_Thread( threading.Thread ):
	def __init__( self, template_id, settings, on_complete ):
		self.template_id	= template_id
		self.settings 		= settings
		self.on_complete	= on_complete
		self.error			= False
		threading.Thread.__init__( self )

	def run( self ):
		store_settings = self.settings.get( 'store' )

		print( 'Retrieving template versions' )

		result, response, error = make_json_request( store_settings, 'Module', '&Count=0&Module_Code=sublime_templateeditor&Module_Function=TemplateVersionList_Load_Template&ManagedTemplate_ID={0}&TemporarySession=1' . format( self.template_id ) )

		if not result:
			self.error = True
			return sublime.error_message( error )

		templateversions = response[ 'data' ][ 'data' ]

		print( 'Retrieved {0} template versions' . format( len( templateversions ) ) )

		sublime.set_timeout( lambda: self.on_complete( templateversions ), 10 )

class Template_Load_ID( threading.Thread ):
	def __init__( self, templ_id, template_name, settings, on_complete ):
		self.templ_id		= templ_id
		self.template_name	= template_name
		self.settings 		= settings
		self.on_complete	= on_complete
		self.error			= False
		threading.Thread.__init__( self )

	def run( self ):
		store_settings = self.settings.get( 'store' )

		print( "Exporting {0}" . format( self.template_name ) )

		result, response, error	= make_json_request( store_settings, 'Module', '&Module_Code=sublime_templateeditor&Module_Function=Template_Load_ID&ManagedTemplateVersion_ID={0}&TemporarySession=1' . format( self.templ_id ) )

		if not result:
			self.error = True
			return sublime.error_message( error )

		template = response[ 'data' ]
		template[ 'template_name' ] = self.template_name

		sublime.set_timeout( lambda: self.on_complete( template ), 10 )

class Template_Write_File( threading.Thread ):
	def __init__( self, template, local_directory, on_complete ):
		self.template 			= template
		self.local_directory	= local_directory
		self.on_complete		= on_complete

		threading.Thread.__init__( self )

	def run( self ):
		file_name 				= '{0}' . format ( self.template[ 'record' ][ 'template_name' ] )
		local_file_path			= os.path.join( self.local_directory, file_name )

		with open( local_file_path, 'w' ) as fh:
				fh.write( self.template[ 'record' ][ 'source' ] )

		sublime.set_timeout( lambda: self.on_complete( self.template ), 10 )

class Template_Update_ID( threading.Thread ):
	def __init__( self, managedtemplate_id, source, settings, on_complete ):
		self.managedtemplate_id		= managedtemplate_id
		self.source			= source
		self.settings		= settings
		self.on_complete	= on_complete
		self.error			= False
		threading.Thread.__init__( self )

	def run( self ):
		store_settings 	= self.settings.get( 'store' )
		source			= urllib.parse.quote_plus( self.source )

		result, response, error	= make_json_request( store_settings, 'Module', '&Module_Code=sublime_templateeditor&Module_Function=Template_Update_ID&ManagedTemplate_ID={0}&Source={1}&TemporarySession=1' . format( self.managedtemplate_id, source ) )

		if not result:
			self.error = True
			return sublime.error_message( error )

		print( 'Page imported' )

class PasswordInputPanel():
	def __init__( self, prompt, on_complete ):
		self.window 		= sublime.active_window()
		self.prompt 		= prompt
		self.on_complete	= on_complete
		self.password 		= ''
		self.stars 			= ''
		self.window.show_input_panel( self.prompt, '', self.on_input, self.getpwd, None )
 
	def getpwd( self, password ):
		chg = password[len(self.stars):]

		if  len( password ) < len( self.password ):
			new_password = self.password[:len( password )]
		else:
			new_password = self.password + chg

		if self.password == new_password:
			return

		self.password 	= new_password
		self.stars 		= "*" * len( password )	
		sublime.set_timeout( lambda: self.window.show_input_panel( self.prompt, self.stars, self.on_input, self.getpwd, None ), 10 )
 
	def on_input( self, password ):
		if self.password.strip() == "":
			self.panel( "No password provided" )
			return

		sublime.set_timeout( lambda: self.on_complete( self.password.strip() ), 10 )

class JSON_Threadpool_Thread( threading.Thread ):
	def __init__( self, settings, parameters, on_complete ):
		self.settings			= settings
		self.parameters 		= parameters
		self.on_complete		= on_complete
		self.error				= False

		threading.Thread.__init__( self )

	def run( self ):
		store_settings 				= self.settings.get( 'store' )
		result, response, error		= make_json_request( store_settings, 'Module', self.parameters )

		if not result:
			self.error = True
			return sublime.error_message( error )

		data = response[ 'data' ]

		sublime.set_timeout( lambda: self.on_complete( data ), 10 )

class JSON_Threadpool():
	def __init__( self, thread_count = 3 ):
		self.thread_count 		= 3
		self.active_count		= 0
		self.running			= False
		self.queue				= []
		self.running_queue		= []
 
	def add_request( self, settings, parameters, on_complete = None ):
		request = JSON_Threadpool_Thread( settings, parameters, lambda data: self.run_request_callback( data, on_complete ) )
		self.queue.append( request )
		self.run()
 
	def run( self ):
		if self.running or len( self.queue ) == 0:
			return

		self.running = True

		for i in range( 0, self.thread_count ):
			if len( self.queue ) > i:
				request = self.queue.pop( 0 )
				self.run_request( request )

	def run_request( self, request ):
		print( 'Running Request' )
		request.start()

	def run_request_callback( self, data, on_complete = None ):
		if on_complete != None:
			sublime.set_timeout( lambda: on_complete( data ), 10 )

		if len( self.queue ) == 0:
			self.running = False
			return

		request = self.queue.pop( 0 )
		self.run_request( request )

json_threadpool = JSON_Threadpool()

#
# Helper Functions
#

#
# Encrypt/Decrypt using OpenSSL -aes128 and -base64
# EG similar to running this CLI command:
#   echo "data" | openssl enc -e -aes128 -base64 -pass "pass:lolcats"
#
def crypto( password, data, enc_flag = '-e' ):
	settings 						= sublime.load_settings( 'MvSublimeTemplateEditor.sublime-settings' )
	cipher 							= settings.get('cipher')
	openssl_command 				= os.path.normpath( settings.get('openssl_command') )

	# pass the password as an ENV variable, for better security
	envVar 							= ''.join( random.sample( string.ascii_uppercase, 23 ) )
	os.environ[ envVar ] 			= password
	_pass 							= "env:%s" % envVar

	try:
		if isinstance(data, str):
			data_handled			= data.encode( 'utf-8' )
		else:
			data_handled			= data

		startupinfo 				= None
		if sublime.platform() == 'windows':
			startupinfo 			= subprocess.STARTUPINFO()
			startupinfo.dwFlags 	|= subprocess.STARTF_USESHOWWINDOW

		openssl 					= Popen( [openssl_command, "enc", enc_flag, cipher, "-base64", "-pass", _pass], startupinfo=startupinfo, stdin=PIPE, stdout=PIPE, stderr=PIPE )

		result, error 				= openssl.communicate( data_handled )

		del os.environ[envVar] # get rid of the temporary ENV var
	except IOError as e:
		return False, None, 'Error: %s' % e
	except OSError as e:
		error_message = """
 Please verify that you have installed OpenSSL.
 Attempting to execute: %s
 Error: %s
		""" % (openssl_command, e[1])
		return False, None, error_message

	# probably a wrong password was entered
	if error:
		_err = error.splitlines()[0]

		if ST3:
			_err = str(_err)

		if _err.find('unknown option') != -1:
			return False, None, 'Error: ' + _err
		elif _err.find("WARNING:") != -1:
			# skip WARNING's
			return True, result, None

		return False, None, 'Error: Wrong password'

	return True, result, None

def join_path( dir_path, file_path, server_type ):
	platform = sublime.platform()

	if server_type == 'windows':
		if dir_path.endswith( '\\' ):
			return dir_path + file_path
		else:
			return dir_path + '\\' + file_path
	elif platform == 'windows':
		if dir_path.endswith( '/' ):
			return dir_path + file_path
		else:
			return dir_path + '/' + file_path

	return os.path.join( dir_path, file_path )

def make_json_request( store_settings, function, other_data = '' ):
		global master_password, openssl_enabled

		store_settings.setdefault( 'store_code', '' )
		store_settings.setdefault( 'json_url', '' )
		store_settings.setdefault( 'username', '' )
		store_settings.setdefault( 'password', '' )
		store_settings.setdefault( 'timeout', 15 )
		store_settings.setdefault( 'password_decrypted', '' )

		store_code	= store_settings[ 'store_code' ]
		json_url 	= store_settings[ 'json_url' ]
		username	= store_settings[ 'username' ]
		password	= store_settings[ 'password' ]
		timeout		= store_settings[ 'timeout' ]

		if openssl_enabled:
			if not 'password_encrypted' in store_settings:
				settings 	= sublime.load_settings( 'MvSublimeTemplateEditor.sublime-settings' )
				sites 		= settings.get( 'sites' )

				success, encrypted_password, error_message = crypto( master_password, password, '-e' )

				if success:
					sites[ store_code ][ 'store' ][ 'password_encrypted' ] 	= True
					sites[ store_code ][ 'store' ][ 'password' ] 			= encrypted_password.decode( encoding='UTF-8')

					self.settings.set( 'sites', sites )
					sublime.save_settings( 'MvSublimeTemplateEditor.sublime-settings' )
			elif store_settings[ 'password_decrypted' ] != '':
				password = store_settings[ 'password_decrypted' ]
			else:
				success, decrypted_password, error_message = crypto( master_password, password, '-d' )

				if success:
					password = decrypted_password.decode( encoding='UTF-8')
					store_settings[ 'password_decrypted' ] = password

		if not json_url.endswith( '?' ):
			json_url += '?'

		url = json_url + 'Store_Code={store_code}&Function={function}&Session_Type=admin&Username={username}&Password={password}' \
			  . format( store_code = urllib.parse.quote_plus( store_code ),  function = urllib.parse.quote_plus( function ), username = urllib.parse.quote_plus( username ), password = urllib.parse.quote_plus( password ) )

		print( url + other_data )

		try:
			req = urllib2.Request( url, other_data.encode( 'utf8' ) )
			request = urllib2.urlopen( req, timeout = timeout )
		except Exception as e:
			print( 'Failed opening URL: {0}' . format( str( e ) ) )
			return False, None, 'Failed to open URL'

		try:
			content = request.read().decode()
		except Exception as e:
			print( 'Failed decoding response: {0}' . format( str( e ) ) )
			return False, None, 'Failed to decode response'

		try:
			json_response 	= json.loads( content )
		except Exception as e:
			print( 'Failed to parse JSON: {0}' . format( str( e ) ) )
			return False, None, 'Failed to parse JSON response'

		if 'success' not in json_response or json_response[ 'success' ] != 1:
			print( 'JSON response was not a success {0}' . format( json_response ) )
			return False, None, json_response[ 'error_message' ]

		return True, json_response, None
