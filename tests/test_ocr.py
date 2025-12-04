# tests/test_ocr.py
import pytest
from ocr_processor import TableFormatter, OCRConfig, TextItem

class TestTableFormatter:
    @pytest.fixture
    def config(self):
        return OCRConfig()

    @pytest.fixture
    def formatter(self, config):
        return TableFormatter(config)

    def test_find_column_boundaries(self, formatter):
        # 這樣平均間距 (avg_gap) 會變小，讓真正的欄位間距 (90, 100) 能被演算法識別
        items = [
            # 第一欄 (x 都在 10 附近)
            TextItem("A1", 10, 0, 30, 10),
            TextItem("A2", 11, 20, 31, 30),
            
            # 第二欄 (x 都在 100 附近)
            TextItem("B1", 100, 0, 120, 10),
            TextItem("B2", 101, 20, 121, 30),
            
            # 第三欄 (x 在 200)
            TextItem("C1", 200, 0, 220, 10),
        ]
        
        boundaries = formatter.find_column_boundaries(items)
        
        # 這樣演算法應該能正確分出三個群集
        assert len(boundaries) == 3
        # 驗證邊界值大約落在哪裡
        assert 10 in boundaries
        assert 100 in boundaries
        assert 200 in boundaries

    def test_assign_cells_to_columns(self, formatter):
        boundaries = [10, 100, 200]
        # 只有第一欄和第三欄有字
        row_items = [
            TextItem("Name", 12, 0, 30, 10),
            TextItem("Date", 205, 0, 230, 10)
        ]
        cells = formatter.assign_cells_to_columns(row_items, boundaries)
        
        assert len(cells) == 3
        assert cells[0] == "Name" # 12 離 10 最近
        assert cells[1] == ""     # 中間沒東西
        assert cells[2] == "Date" # 205 離 200 最近

    def test_is_continuous_content(self, formatter):
        # 測試日期連續性判斷
        assert formatter._is_continuous_content("2023-", "11") is True
        assert formatter._is_continuous_content("Step ", "1") is False
