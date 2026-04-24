# Scrapegraph Demo Merge Notes

This project now contains three core capabilities migrated from `scrapegraph_demo`:

1. `news_search` ingest source using DuckDuckGo news search with strict publication-date validation.
2. Feishu interactive card notifications with optional local infographic generation.
3. Regression tests for the news freshness heuristics in `tests/test_news_search_fetcher.py`.

## 1. Install additional dependencies

```bash
pip install -r requirements.txt
```

The new features use:

- `ddgs`
- `Pillow`

## 2. Example search source

Add this block to `sources.yaml` when you want search-driven news ingestion:

```yaml
search_news:
  - name: "AI Search Radar"
    type: news_search
    query: "OpenAI Google Meta Anthropic AI model launch release"
    authority_score: 72
    tags: [news, search, launch]
    region: "us-en"
    timelimit: "d"
    max_results: 5
    max_age_hours: 48
    enabled: true
```

## 3. Example Feishu notification config

Add this block to `rules.yaml` when you want Feishu delivery:

```yaml
notify:
  feishu_enabled: true
  feishu_include_infographic: true
  feishu_image_output_dir: "outputs/feishu"
  feishu_max_items: 3
```

And set the environment variables:

```powershell
$env:FEISHU_WEBHOOK_URL="https://open.feishu.cn/open-apis/bot/v2/hook/..."
$env:FEISHU_APP_ID="cli_..."
$env:FEISHU_APP_SECRET="..."
```

`FEISHU_APP_ID` and `FEISHU_APP_SECRET` are only required if you want image upload.

## 4. Run daily digest

```bash
python -m src.main daily --no-summary
```

Or keep LLM summaries enabled:

```bash
python -m src.main daily
```

### LLM `.env` examples

Third-party OpenAI-compatible proxy:

```env
AI_INTAKE_LLM_PROVIDER=openai_compatible
AI_INTAKE_LLM_MODEL=gpt-5.4
OPENAI_API_KEY=your_proxy_key
OPENAI_BASE_URL=http://your-proxy-host:4000/v1
```

Local Ollama:

```env
AI_INTAKE_LLM_PROVIDER=ollama
AI_INTAKE_LLM_MODEL=qwen2.5:14b
OLLAMA_BASE_URL=http://localhost:11434
OLLAMA_MODEL=qwen2.5:14b
```

## 5. Notes

- The original `scrapegraph_demo` repository is untouched.
- `ai-intake` remains independently runnable with its existing RSS/GitHub pipeline.
- The new `news_search` source is optional and does not affect existing sources unless you enable it.
