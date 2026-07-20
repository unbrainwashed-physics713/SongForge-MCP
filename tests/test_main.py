def test_main_module_registers_all_tools_on_import():
    import vocal_synth_mcp.main as main_module

    names = {t.name for t in main_module.mcp._tool_manager.list_tools()}
    assert {"synthesize_vocal", "list_voicebanks", "validate_score"} <= names
