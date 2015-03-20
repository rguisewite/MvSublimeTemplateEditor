MVC=$(shell which mvc)
CFLAGS=-C 5.20 -W all -p all

sublime_templateeditor.mvc: sublime_templateeditor.mv
	cat sublime_templateeditor.mv > temp.mv
	cat /path/to/features/tui/tui_db.mv | \
	sed -e 's#\<MvINCLUDE FILE = \"build_ident.mv\">##' | \
	sed -e 's#\(ManagedTemplate_Read.*\)#\1<MvEVAL EXPR = \"\{ TemplateEditorSession_AppendTemplateID( ManagedTemplates.d.id ) \}\">#' | \
	sed -e 's#\(ManagedTemplateVersion_Read.*\)#\1<MvEVAL EXPR = \"\{ TemplateEditorSession_AppendTemplateID( ManagedTemplateVersions.d.templ_id ) \}\">#' >> temp.mv;
	$(MVC) $(CFLAGS) temp.mv
	mv temp.mvc ../bin/sublime_templateeditor.mvc
	rm temp.mv

deploy: 