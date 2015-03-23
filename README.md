# MvSublimeTemplateEditor
Sublime Text 3 Plugin for Miva Web Developers

This Sublime Text plugin allows Miva Web Developers to edit store pages/templates directly from Sublime.  Developers can pull up the list of pages/templates in a store, select one, and then edit it directly from Sublime.

Download the zip file. Extract the src/ directory, rename it to MvSublimeTemplateEditor, and copy it into one of the following directories:

Ubuntu: ~/.config/sublime-text-3/Packages/

OS X: ~/Library/Application Support/Sublime Text 3/Packages/

Windows: %APPDATA%\Sublime Text 3\Packages\

Note: For Windows, you will need to add a trailing "/" to the template export path (example: "C:\\\\TEMP\\\\" or "/c/TEMP/").
Also, openssl binaries are available for Windows systems if you wish to use the password encryption functionality (see here: https://www.openssl.org/related/binaries.html). Simply extract the openssl.exe and update the path in your sublime settings.

This plugin will save Store passwords as encrypted strings (given a master password you enter when the functionality is enabled). To use this feature, your system MUST have OpenSSL installed. If it does not, you can either install it, or disable the password encryption by adding '"disable_master_password": true' to your preferences

You must also add the compiled version (.mvc) of the sublime_templateeditor module into the host store (simply add it to the Modules screen) located in the bin/ directory
