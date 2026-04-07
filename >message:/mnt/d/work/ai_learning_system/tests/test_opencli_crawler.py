: "import pytest
from unittest.mock import patch, MagicMock

from src.models import SourceType, DocFormat
from src.crawler.opencli import OpenCLICrawler, OpenCLIError


def test_source_type_opencli_exists():
    """测试 SourceType 包含 OPENCLI"""
    assert SourceType.OPENCLI.value == "opencli"
    assert hasattr(SourceType, "OPENCLI")


def test_opencli_crawler_can_be_instantiated():
    """测试 OpenCLICrawler 可被实例化"""
    crawler = OpenCLICrawler()
    assert crawler is not None


def test_opencli_crawler_has_whitelist():
    """测试 OpenCLICrawler 有白名单配置"""
    crawler = OpenCLICrawler()
    assert hasattr(crawler, "whitelist")
    assert isinstance(crawler.whitelist, set)
    assert len(crawler.whitelist) > 0


def test_parse_url_xiaohongshu_note():
    """测试解析小红书笔记 URL"""
    crawler = OpenCLICrawler()
    result = crawler._parse_url("opencli://xiaohongshu/note/abc123")

    assert result["site"] == "xiaohongshu"
    assert result["command"] == "note"
    assert result["arg"] == "abc123"
    assert result["params"] == {}


def test_parse_url_zhihu_download():
    """测试解析知乎下载 URL"""
    crawler = OpenCLICrawler()
    result = crawler._parse_url("opencli://zhihu/download?url=https://example.com")

    assert result["site"] == "zhihu"
    assert result["command"] == "download"
    assert result["arg"] is None
    assert result["params"] == {"url": ["https://example.com"]}


def test_check_whitelist_allowed():
    """测试白名单允许通过的命令"""
    crawler = OpenCLICrawler()

    # 应该通过
    assert crawler._check_whitelist("xiaohongshu", "note", "abc123") is True
    assert crawler._check_whitelist("bilibili", "subtitle", "BV1xx") is True
    assert crawler._check_whitelist("zhihu", "download", None) is True


def test_check_whitelist_blocked():
    """测试白名单拒绝的命令"""
    crawler = OpenCLICrawler()

    # 应该拒绝
    assert crawler._check_whitelist("bilibili", "hot", None) is False
    assert crawler._check_whitelist("hackernews", "top", None) is False
    assert crawler._check_whitelist("zhihu", "search", None) is False


def test_parse_url_invalid_scheme():
    """测试无效 URL scheme"""
    crawler = OpenCLICrawler()
    with pytest.raises(ValueError, match="Invalid opencli URL"):
        crawler._parse_url("http://example.com")


def test_parse_url_missing_site():
    """测试缺少 site"""
    crawler = OpenCLICrawler()
    with pytest.raises(ValueError, match="Missing site"):
        crawler._parse_url("opencli:///command")


def test_parse_url_missing_command():
    """测试缺少 command"""
    crawler = OpenCLICrawler()
    with pytest.raises(ValueError, match="Missing command"):
        crawler._parse_url("opencli://xiaohongshu")


def test_parse_bilibili_subtitle_output():
    """测试解析 bilibili subtitle 输出"""
    crawler = OpenCLICrawler()

    mock_data = {
        "bvid": "BV1xx411c7mD",
        "title": "测试视频",
        "subtitles": [
            {"start": 0, "end": 5, "text": "你好"},
            {"start": 5, "end": 10, "text": "世界"},
        ],
    }

    doc = crawler._parse_stdout_content("bilibili", "subtitle", mock_data)

    assert doc.title == "测试视频"
    assert "你好" in doc.content
    assert "世界" in doc.content
    assert doc.format == DocFormat.TEXT
    assert doc.source_type == SourceType.OPENCLI


def test_parse_xiaohongshu_note_output():
    """测试解析小红书笔记输出"""
    crawler = OpenCLICrawler()

    mock_data = {
        "title": "笔记标题",
        "content": "笔记正文内容...",
        "author": "作者名",
        "url": "https://www.xiaohongshu.com/...",
    }

    doc = crawler._parse_stdout_content("xiaohongshu", "note", mock_data)

    assert doc.title == "笔记标题"
    assert doc.content == "笔记正文内容..."
    assert doc.format == DocFormat.TEXT
    assert doc.source_type == SourceType.OPENCLI


def test_parse_file_output_zhihu(tmp_path):
    """测试解析知乎下载命令生成的文件"""
    crawler = OpenCLICrawler()
    
    # 创建模拟的 markdown 文件
    md_file = tmp_path / "test_zhihu.md"
    md_file.write_text("# 知乎文章标题\n\n这是文章内容。\n", encoding='utf-8')
    
    doc = crawler._parse_file_output(
        str(tmp_path),
        'zhihu',
        'download',
        {'url': ['https://zhuanlan.zhihu.com/p/123']}
    )
    
    assert doc.title == '知乎文章标题'
    assert '知乎文章标题' in doc.content
    assert doc.format == DocFormat.MARKDOWN
    assert doc.source_type == SourceType.OPENCLI


def test_parse_file_output_no_markdown(tmp_path):
    """测试目录中没有 markdown 文件时的错误处理"""
    crawler = OpenCLICrawler()
    
    with pytest.raises(OpenCLIError) as exc_info:
        crawler._parse_file_output(
            str(tmp_path),
            'zhihu',
            'download',
            {'url': ['https://example.com']}
        )
    
    assert '未找到导出文件' in str(exc_info.value)


def test_execute_opencli_command_success():
    """测试成功执行 opencli 命令"""
    crawler = OpenCLICrawler()
    
    mock_process = MagicMock()
    mock_process.returncode = 0
    mock_process.stdout = '{"title": "Test", "content": "Content"}'
    mock_process.stderr = ''
    
    with patch('subprocess.run', return_value=mock_process) as mock_run:
        result = crawler._execute_command(['opencli', 'xiaohongshu', 'note', 'abc123'])
        
        assert result == '{"title": "Test", "content": "Content"}'
        mock_run.assert_called_once()


def test_execute_opencli_command_not_found():
    """测试 opencli 未安装的情况"""
    crawler = OpenCLICrawler()
    
    with patch('subprocess.run', side_effect=FileNotFoundError()):
        with pytest.raises(OpenCLIError) as exc_info:
            crawler._execute_command(['opencli', 'xiaohongshu', 'note', 'abc123'])
        
        assert '未安装' in str(exc_info.value)


def test_execute_opencli_browser_not_connected():
    """测试浏览器扩展未连接的情况 (exit code 69)"""
    crawler = OpenCLICrawler()
    
    mock_process = MagicMock()
    mock_process.returncode = 69
    mock_process.stdout = ''
    mock_process.stderr = 'Browser Bridge not connected'
    
    with patch('subprocess.run', return_value=mock_process):
        with pytest.raises(OpenCLIError) as exc_info:
            crawler._execute_command(['opencli', 'xiaohongshu', 'note', 'abc123'])
        
        assert '浏览器扩展未连接' in str(exc_info.value)
        assert exc_info.value.exit_code == 69


def test_execute_opencli_auth_required():
    """测试需要登录的情况 (exit code 77)"""
    crawler = OpenCLICrawler()
    
    mock_process = MagicMock()
    mock_process.returncode = 77
    mock_process.stdout = ''
    mock_process.stderr = 'Authentication required'
    
    with patch('subprocess.run', return_value=mock_process):
        with pytest.raises(OpenCLIError) as exc_info:
            crawler._execute_command(['opencli', 'xiaohongshu', 'note', 'abc123'])
        
        assert '登录态' in str(exc_info.value) or '认证' in str(exc_info.value)
        assert exc_info.value.exit_code == 77
