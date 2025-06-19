"""
Unit tests for tag_utils module
"""

import pytest
from unittest.mock import Mock, patch
from tag_utils import parse_tags, format_tags, extract_tags


class TestParseTags:
    """Test the parse_tags function"""
    
    @pytest.mark.unit
    def test_parse_tags_basic(self):
        """Test basic tag parsing"""
        result = parse_tags("web;database;production")
        assert result == ["web", "database", "production"]
    
    @pytest.mark.unit
    def test_parse_tags_with_spaces(self):
        """Test parsing tags with extra spaces"""
        result = parse_tags(" web ; database ; production ")
        assert result == ["web", "database", "production"]
    
    @pytest.mark.unit
    def test_parse_tags_empty_string(self):
        """Test parsing empty string"""
        result = parse_tags("")
        assert result == []
    
    @pytest.mark.unit
    def test_parse_tags_none(self):
        """Test parsing None value"""
        result = parse_tags(None)
        assert result == []
    
    @pytest.mark.unit
    def test_parse_tags_non_string(self):
        """Test parsing non-string input"""
        result = parse_tags(123)
        assert result == []
    
    @pytest.mark.unit
    def test_parse_tags_single_tag(self):
        """Test parsing single tag"""
        result = parse_tags("production")
        assert result == ["production"]
    
    @pytest.mark.unit
    def test_parse_tags_empty_tags_filtered(self):
        """Test that empty tags are filtered out"""
        result = parse_tags("web;;database;")
        assert result == ["web", "database"]
    
    @pytest.mark.unit
    def test_parse_tags_whitespace_only_filtered(self):
        """Test that whitespace-only tags are filtered out"""
        result = parse_tags("web;  ;database;   ")
        assert result == ["web", "database"]
    
    @pytest.mark.unit
    def test_parse_tags_semicolon_only(self):
        """Test parsing string with only semicolons"""
        result = parse_tags(";;;")
        assert result == []


class TestFormatTags:
    """Test the format_tags function"""
    
    @pytest.mark.unit
    def test_format_tags_basic(self):
        """Test basic tag formatting"""
        result = format_tags(["web", "database", "production"])
        assert result == "web;database;production"
    
    @pytest.mark.unit
    def test_format_tags_empty_list(self):
        """Test formatting empty list"""
        result = format_tags([])
        assert result == ""
    
    @pytest.mark.unit
    def test_format_tags_none(self):
        """Test formatting None value"""
        result = format_tags(None)
        assert result == ""
    
    @pytest.mark.unit
    def test_format_tags_single_tag(self):
        """Test formatting single tag"""
        result = format_tags(["production"])
        assert result == "production"
    
    @pytest.mark.unit
    def test_format_tags_with_spaces(self):
        """Test formatting tags with spaces"""
        result = format_tags([" web ", " database ", " production "])
        assert result == "web;database;production"
    
    @pytest.mark.unit
    def test_format_tags_empty_tags_filtered(self):
        """Test that empty tags are filtered out"""
        result = format_tags(["web", "", "database", None])
        assert result == "web;database"
    
    @pytest.mark.unit
    def test_format_tags_whitespace_only_filtered(self):
        """Test that whitespace-only tags are filtered out"""
        result = format_tags(["web", "  ", "database", "   "])
        assert result == "web;database"
    
    @pytest.mark.unit
    def test_format_tags_non_string_converted(self):
        """Test that non-string values are converted to strings"""
        result = format_tags(["web", 123, "database"])
        assert result == "web;123;database"
    
    @pytest.mark.unit
    def test_format_tags_mixed_types(self):
        """Test formatting mixed data types"""
        result = format_tags(["web", 123, True, "database"])
        assert result == "web;123;True;database"


class TestExtractTags:
    """Test the extract_tags function"""
    
    @pytest.mark.unit
    def test_extract_tags_basic(self, sample_vms):
        """Test basic tag extraction from VM list"""
        result = extract_tags(sample_vms)
        expected = ["api", "backend", "database", "development", "frontend", "monitoring", "production", "web"]
        assert result == expected
    
    @pytest.mark.unit
    def test_extract_tags_empty_list(self):
        """Test extraction from empty VM list"""
        result = extract_tags([])
        assert result == []
    
    @pytest.mark.unit
    def test_extract_tags_no_tags(self):
        """Test extraction from VMs with no tags"""
        vms = [
            {"vmid": 100, "name": "test-vm-1", "tags": ""},
            {"vmid": 101, "name": "test-vm-2", "tags": None},
            {"vmid": 102, "name": "test-vm-3"}  # No tags field
        ]
        result = extract_tags(vms)
        assert result == []
    
    @pytest.mark.unit
    def test_extract_tags_duplicate_removal(self):
        """Test that duplicate tags are removed"""
        vms = [
            {"vmid": 100, "tags": "web;production"},
            {"vmid": 101, "tags": "database;production"},
            {"vmid": 102, "tags": "web;api"}
        ]
        result = extract_tags(vms)
        assert result == ["api", "database", "production", "web"]
    
    @pytest.mark.unit
    def test_extract_tags_case_preservation(self):
        """Test that original case is preserved"""
        vms = [
            {"vmid": 100, "tags": "Web;Production"},
            {"vmid": 101, "tags": "Database;API"}
        ]
        result = extract_tags(vms)
        assert result == ["API", "Database", "Production", "Web"]
    
    @pytest.mark.unit
    def test_extract_tags_whitespace_handling(self):
        """Test handling of whitespace in tags"""
        vms = [
            {"vmid": 100, "tags": " web ; production "},
            {"vmid": 101, "tags": "database;  ;api"}
        ]
        result = extract_tags(vms)
        assert result == ["api", "database", "production", "web"]
    
    @pytest.mark.unit
    def test_extract_tags_non_string_tags(self):
        """Test handling of non-string tag values"""
        vms = [
            {"vmid": 100, "tags": 123},
            {"vmid": 101, "tags": ["web", "production"]},
            {"vmid": 102, "tags": "database;api"}
        ]
        result = extract_tags(vms)
        # Only string tags should be processed
        assert result == ["api", "database"]
    
    @pytest.mark.unit
    def test_extract_tags_exception_handling(self, mock_logger):
        """Test exception handling in extract_tags"""
        # Test with data that causes an exception in the split operation
        # Mock vm.get to raise an exception
        problematic_vm = Mock()
        problematic_vm.get.side_effect = Exception("Test exception")
        vms = [problematic_vm]
        
        with patch('tag_utils.logging') as mock_logging:
            result = extract_tags(vms)
            
            # Should return empty list on exception
            assert result == []
            
            # Should log the error
            mock_logging.error.assert_called_once()
            error_msg = mock_logging.error.call_args[0][0]
            assert "Error extracting tags" in error_msg
            assert "Test exception" in error_msg


class TestTagUtilsIntegration:
    """Integration tests for tag utils functions working together"""
    
    @pytest.mark.unit
    def test_parse_format_roundtrip(self):
        """Test that parse and format are complementary operations"""
        original_tags = ["web", "database", "production"]
        formatted = format_tags(original_tags)
        parsed = parse_tags(formatted)
        assert parsed == original_tags
    
    @pytest.mark.unit
    def test_extract_format_integration(self, sample_vms):
        """Test extract_tags with format_tags"""
        extracted = extract_tags(sample_vms)
        formatted = format_tags(extracted)
        reparsed = parse_tags(formatted)
        assert reparsed == extracted
    
    @pytest.mark.unit
    def test_empty_values_consistency(self):
        """Test consistent handling of empty values across functions"""
        # All these should result in empty results
        assert parse_tags("") == []
        assert parse_tags(None) == []
        assert format_tags([]) == ""
        assert format_tags(None) == ""
        assert extract_tags([]) == []
    
    @pytest.mark.unit
    def test_tag_normalization_consistency(self):
        """Test that tag normalization is consistent across functions"""
        tags_with_spaces = [" web ", " database ", "  production  "]
        formatted = format_tags(tags_with_spaces)
        assert formatted == "web;database;production"
        
        parsed = parse_tags(" web ; database ;  production  ")
        assert parsed == ["web", "database", "production"]