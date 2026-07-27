def test_main_module_registers_all_tools_on_import():
    import songforge_mcp.main as main_module

    names = {t.name for t in main_module.mcp._tool_manager.list_tools()}
    assert {"generate_vocal_track", "split_vocal_stems"} <= names
