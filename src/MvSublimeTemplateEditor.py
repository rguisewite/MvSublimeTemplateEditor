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

#
# Pages / Items Quick Panel Load
#

class MvSublimeTemplateEditorGetSitesCommand( sublime_plugin.WindowCommand ):
	def run( self, type = 'pages' ):
		self.type		= type
		self.settings 	= sublime.load_settings( 'MvSublimeTemplateEditor.sublime-settings' )
		sites			= []

		for site in self.settings.get( 'sites', [] ):
			sites.append( site[ 'name' ] )

		if not sites:
			sublime.error_message( 'No sites configured' )
			return

		sublime.set_timeout( lambda: self.window.show_quick_panel( sites, lambda index: self.site_callback( sites, index ) ) )

	def site_callback( self, sites, index ):
		if index == -1:
			return

		if self.type == 'pages':
			self.window.run_command( 'mv_sublime_template_editor_get_pages', { 'site': sites[ index ] } )
		elif self.type == 'templates':
			self.window.run_command( 'mv_sublime_template_editor_get_templates', { 'site': sites[ index ] } )

class MvSublimeTemplateEditorGetPagesCommand( sublime_plugin.WindowCommand ):
	def run( self, site = None ):
		self.site = site
		settings = sublime.load_settings( 'MvSublimeTemplateEditor.sublime-settings' )

		if site is None:
			if settings.get( 'sites' ) is not None:
				return self.window.run_command( 'mv_sublime_template_editor_get_sites', { 'type': 'pages' } )

			self.settings = settings
		else:
			try:
				for site_settings in settings.get( 'sites', [] ):
					if site_settings[ 'name' ] == site:
						self.settings = site_settings
						break
			except KeyError:
				sublime.error_message( 'Site not found' )
				return
			except Exception:
				sublime.error_message( 'Invalid configuration file' )
				return

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

		page_code 	= pages[ index ][ 'page_code' ]
		page_templ_current_id	= pages[ index ][ 'page_templ_current_id' ]
		thread 		= TemplateExportThread( page_templ_current_id, page_code, self.settings, on_complete = self.download_page )
		thread.start()
		ThreadProgress( thread, 'Exporting {0}' . format( page_code ), '{0} exported' . format( page_code ), 'Export of {0} failed' . format( page_code ) )

	def download_page( self, template ):
		local_directory		= self.settings.get( 'local_exported_templates', '' )
		file_name 			= '{0}-page.htm' . format ( template[ 'template_name' ] )
		local_file_path		= os.path.join( local_directory, file_name )
		with open( local_file_path, 'w' ) as fh:
				fh.write( template[ 'source' ] )
		view = self.window.open_file( local_file_path )
		view_settings = view.settings()
		view_settings.set( 'miva_managedtemplateversion', "true" )
		view_settings.set( 'miva_managedtemplateversion_template', template )
		view_settings.set( 'miva_site', self.site )

	def show_quick_panel( self, entries, on_select, on_highlight = None ):
		sublime.set_timeout( lambda: self.window.show_quick_panel( entries, on_select, on_highlight = on_highlight ), 10 )

class MvSublimeTemplateEditorGetTemplatesCommand( sublime_plugin.WindowCommand ):
	def run( self, site = None ):
		self.site = site
		settings = sublime.load_settings( 'MvSublimeTemplateEditor.sublime-settings' )

		if site is None:
			if settings.get( 'sites' ) is not None:
				return self.window.run_command( 'mv_sublime_template_editor_get_sites', { 'type': 'templates' } )

			self.settings = settings
		else:
			try:
				for site_settings in settings.get( 'sites', [] ):
					if site_settings[ 'name' ] == site:
						self.settings = site_settings
						break
			except KeyError:
				sublime.error_message( 'Site not found' )
				return
			except Exception:
				sublime.error_message( 'Invalid configuration file' )
				return

		thread = TemplateList_Load_All_Thread( self.settings, on_complete = self.templates_quick_panel )
		thread.start()
		ThreadProgress( thread, 'Loading templates', error_message = 'Failed loading templates' )

	def templates_quick_panel( self, templates ):
		entries = []

		for template in templates:
			entries.extend( [ 'Template file - {0}' . format( template[ 'filename' ] ) ] )

		self.show_quick_panel( entries, lambda index: self.templates_callback( templates, index ) )

	def templates_callback( self, templates, index ):
		if index == -1:
			return

		filename 			= templates[ index ][ 'filename' ]
		current_id			= templates[ index ][ 'current_id' ]
		thread 				= TemplateExportThread( current_id, filename, self.settings, on_complete = self.download_template )
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
		view_settings.set( 'miva_site', self.site )

	def show_quick_panel( self, entries, on_select, on_highlight = None ):
		sublime.set_timeout( lambda: self.window.show_quick_panel( entries, on_select, on_highlight = on_highlight ), 10 )

#
# Template Menu
#

class MvSublimeTemplateEditorTemplateMenu( sublime_plugin.WindowCommand ):
	def run( self ):
		self.view			= self.window.active_view()
		self.view_settings	= self.view.settings()

		if not self.view_settings.has( 'miva_managedtemplateversion' ):
			return

		self.settings 	= sublime.load_settings( 'MvSublimeTemplateEditor.sublime-settings' )
		self.site		= self.view_settings.get( 'miva_site' )

		if self.site is None:
			return
		else:
			try:
				for site_settings in self.settings.get( 'sites', [] ):
					if site_settings[ 'name' ] == self.site:
						self.settings = site_settings
						break
			except KeyError:
				sublime.error_message( 'Site not found' )
				return
			except Exception:
				sublime.error_message( 'Invalid configuration file' )
				return

		commands		= [ 'Commit', 'Versions' ]

		sublime.set_timeout( lambda: self.window.show_quick_panel( commands, lambda index: self.command_callback( commands, index ) ) )

	def command_callback( self, commands, index ):
		if index == -1:
			return

		if commands[ index ] == 'Commit':
			self.on_save( self.view )
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
		thread 				= TemplateSaveID( template[ 'templ_id' ], source, self.settings, on_complete = None )
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
		thread 				= TemplateExportThread( current_id, "{0}-{1}" . format( filename, current_id ), self.settings, on_complete = self.download_template )
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
		view_settings.set( 'miva_site', self.site )

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

class TemplateExportThread( threading.Thread ):
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
		print( "{0}" . format( template[ 'id' ] ) )

		print( 'Page exported' )

		sublime.set_timeout( lambda: self.on_complete( template ), 10 )

class FileDownloadThread( threading.Thread ):
	def __init__( self, file_name, settings, on_complete ):
		self.file_name		= file_name
		self.settings		= settings
		self.on_complete	= on_complete
		self.error			= False
		threading.Thread.__init__( self )

	def run( self ):
		ftp_settings = self.settings.get( 'ftp', {} )

		ftp_settings.setdefault( 'host', '' )
		ftp_settings.setdefault( 'username', '' )
		ftp_settings.setdefault( 'password', '' )
		ftp_settings.setdefault( 'exported_templates', '' )
		ftp_settings.setdefault( 'server_type', 'unix' )
		ftp_settings.setdefault( 'timeout', 15 )

		server_directory	= ftp_settings[ 'exported_templates' ]
		local_directory		= self.settings.get( 'local_exported_templates', '' )

		server_file_path 	= join_path( server_directory, self.file_name, ftp_settings[ 'server_type' ] )
		local_file_path		= os.path.join( local_directory, self.file_name )
		ftp 				= FTP( ftp_settings[ 'host' ], ftp_settings[ 'username' ], ftp_settings[ 'password' ], ftp_settings[ 'timeout' ] )

		print( 'Downloading file {0}' . format( server_file_path ) )

		if not ftp.download_file( server_file_path, local_file_path ):
			self.error = True
			return sublime.error_message( ftp.error )

		print( 'Downloaded complete' )

		sublime.set_timeout( lambda: self.on_complete( local_file_path ) )

class TemplateSaveID( threading.Thread ):
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

#
# Helper Functions
#

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

def determine_settings( dir_name ):
	settings 	= sublime.load_settings( 'MvSublimeTemplateEditor.sublime-settings' )
	sites		= settings.get( 'sites' )

	if sites is None:
		return settings

	try:
		for site in sites:
			if site[ 'local_exported_templates' ] == dir_name:
				return site
	except:
		pass

	return None

def make_json_request( store_settings, function, other_data = '' ):
		store_settings.setdefault( 'store_code', '' )
		store_settings.setdefault( 'json_url', '' )
		store_settings.setdefault( 'username', '' )
		store_settings.setdefault( 'password', '' )
		store_settings.setdefault( 'timeout', 15 )

		store_code	= store_settings[ 'store_code' ]
		json_url 	= store_settings[ 'json_url' ]
		username	= store_settings[ 'username' ]
		password	= store_settings[ 'password' ]
		timeout		= store_settings[ 'timeout' ]

		if not json_url.endswith( '?' ):
			json_url += '?'

		url = json_url + 'Store_Code={store_code}&Function={function}&Session_Type=admin&Username={username}&Password={password}' \
			  . format( store_code = urllib.parse.quote_plus( store_code ),  function = urllib.parse.quote_plus( function ), username = urllib.parse.quote_plus( username ), password = urllib.parse.quote_plus( password ) )

		try:
			req = urllib2.Request( url, other_data.encode( 'utf8' ) )
			#request = urllib.request.urlopen( url, timeout = timeout )
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
