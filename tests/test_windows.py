from unittest.mock import patch, MagicMock

def test_apply_windows_patches_is_importable():
    from hermes_cli.platform.windows import apply_windows_patches
    assert callable(apply_windows_patches)

def test_normalize_path_converts_backslashes():
    from hermes_cli.platform.windows import normalize_path
    result = normalize_path(r"C:\Users\test\project")
    assert "\\" not in result

def test_normalize_path_accepts_forward_slashes():
    from hermes_cli.platform.windows import normalize_path
    result = normalize_path("C:/Users/test/project")
    assert result == "C:/Users/test/project"

def test_apply_windows_patches_calls_colorama_init():
    with patch("hermes_cli.platform.windows.colorama") as mock_colorama, \
         patch("hermes_cli.platform.windows.asyncio"):
        from hermes_cli.platform.windows import apply_windows_patches
        apply_windows_patches()
        mock_colorama.init.assert_called_once_with(wrap=True)

def test_apply_windows_patches_sets_proactor_policy():
    with patch("hermes_cli.platform.windows.asyncio") as mock_asyncio:
        mock_policy = MagicMock()
        mock_asyncio.WindowsProactorEventLoopPolicy.return_value = mock_policy
        from hermes_cli.platform.windows import apply_windows_patches
        apply_windows_patches()
        mock_asyncio.set_event_loop_policy.assert_called_once_with(mock_policy)

def test_apply_windows_patches_skips_colorama_when_unavailable():
    """Graceful degradation when colorama is not installed."""
    with patch("hermes_cli.platform.windows.colorama", None), \
         patch("hermes_cli.platform.windows.asyncio"):
        from hermes_cli.platform.windows import apply_windows_patches
        apply_windows_patches()  # must not raise AttributeError
