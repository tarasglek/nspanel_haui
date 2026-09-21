from pathlib import Path


ROOT = Path(__file__).parents[1]


def test_all_tft_upload_paths_stop_buzzer_before_blocking_transfer():
    common = (ROOT / "esphome/nspanel_haui/scripts_common.yaml").read_text()
    api = (ROOT / "esphome/nspanel_haui/api.yaml").read_text()
    button = (ROOT / "esphome/nspanel_haui/button.yaml").read_text()

    safe_upload = """  - id: upload_tft_safe
    then:
      - rtttl.stop:
      - output.turn_off: haui_rtttl_out
      - delay: 100ms
      - lambda: id(haui_disp).upload_tft();
"""
    assert safe_upload in common
    assert api.count("        - script.execute: upload_tft_safe") == 2
    assert "      - script.execute: upload_tft_safe" in button
    assert "id(haui_disp).upload_tft()" not in api
    assert "id(haui_disp).upload_tft()" not in button
