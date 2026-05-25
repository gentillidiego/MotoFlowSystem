from utils import to_float, get_gdrive_folder_id

def test_to_float_formats():
    assert to_float("1250.50") == 1250.5
    assert to_float("1.250,50") == 1250.5
    assert to_float("R$ 1.250,50") == 1250.5
    assert to_float("  500,00  ") == 500.0
    assert to_float("invalido") is None
    assert to_float("") == 0.0

def test_get_gdrive_folder_id():
    url1 = "https://drive.google.com/drive/folders/1abc-def_ghi"
    url2 = "https://drive.google.com/open?id=2xyz-uvw_123"
    
    assert get_gdrive_folder_id(url1) == "1abc-def_ghi"
    assert get_gdrive_folder_id(url2) == "2xyz-uvw_123"
    assert get_gdrive_folder_id("link-ruim") is None
    assert get_gdrive_folder_id("") is None
