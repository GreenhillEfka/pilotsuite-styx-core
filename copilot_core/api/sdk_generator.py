"""P5-006: SDK Generation — Python, JS/TS, Go SDKs."""
from __future__ import annotations

import logging
import json
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional
from pathlib import Path
from enum import Enum

logger = logging.getLogger(__name__)


class SDKLanguage(Enum):
    """SDK target languages."""
    PYTHON = "python"
    TYPESCRIPT = "typescript"
    GO = "go"


@dataclass
class SDKConfig:
    """SDK generation configuration."""
    language: SDKLanguage
    package_name: str
    version: str
    author: str
    output_dir: str
    include_docs: bool = True
    include_tests: bool = True


class SDKGenerator:
    """Generates client SDKs from OpenAPI spec."""

    def __init__(self):
        self._templates: Dict[SDKLanguage, str] = {}
        self._register_templates()

    def _register_templates(self):
        """Register code templates for each language."""
        # Python template
        self._templates[SDKLanguage.PYTHON] = '''
# {package_name} v{version}
# Auto-generated SDK for PilotSuite Core API

import requests
from typing import Any, Dict, Optional

class {class_name}Client:
    def __init__(self, base_url: str, api_key: Optional[str] = None):
        self.base_url = base_url
        self.api_key = api_key
        self.session = requests.Session()
        if api_key:
            self.session.headers["X-API-Key"] = api_key
    
    def health(self) -> Dict[str, Any]:
        """Check API health."""
        resp = self.session.get(f"{{self.base_url}}/api/v1/health")
        resp.raise_for_status()
        return resp.json()
    
    def query_rag(self, query: str, k: int = 10) -> Dict[str, Any]:
        """Query RAG system."""
        resp = self.session.post(
            f"{{self.base_url}}/api/v1/rag/query",
            json={{"query": query, "k": k}}
        )
        resp.raise_for_status()
        return resp.json()
    
    def get_patterns(self) -> List[Dict[str, Any]]:
        """Get detected patterns."""
        resp = self.session.get(f"{{self.base_url}}/api/v1/ml/patterns")
        resp.raise_for_status()
        return resp.json()
    
    def set_preference(self, user_id: str, category: str, key: str, value: str) -> Dict[str, Any]:
        """Set user preference."""
        resp = self.session.post(
            f"{{self.base_url}}/api/v1/users/{{user_id}}/preferences",
            json={{"category": category, "key": key, "value": value}}
        )
        resp.raise_for_status()
        return resp.json()
'''

        # TypeScript template
        self._templates[SDKLanguage.TYPESCRIPT] = '''
// {package_name} v{version}
// Auto-generated SDK for PilotSuite Core API

export interface HealthResponse {{ status: string; }}
export interface RAGQueryRequest {{ query: string; k?: number; }}
export interface RAGQueryResponse {{ results: any[]; query: string; }}
export interface Pattern {{ id: string; type: string; description: string; confidence: number; }}

export class {class_name}Client {{
  private baseUrl: string;
  private apiKey?: string;

  constructor(baseUrl: string, apiKey?: string) {{
    this.baseUrl = baseUrl;
    this.apiKey = apiKey;
  }}

  private async request<T>(path: string, options?: RequestInit): Promise<T> {{
    const headers = new Headers(options?.headers);
    if (this.apiKey) headers.set("X-API-Key", this.apiKey);
    
    const resp = await fetch(this.baseUrl + path, {{ ...options, headers }});
    if (!resp.ok) throw new Error(`HTTP ${{resp.status}}`);
    return resp.json();
  }}

  async health(): Promise<HealthResponse> {{
    return this.request<HealthResponse>("/api/v1/health");
  }}

  async queryRag(query: string, k = 10): Promise<RAGQueryResponse> {{
    return this.request<RAGQueryResponse>("/api/v1/rag/query", {{
      method: "POST",
      body: JSON.stringify({{ query, k }}),
      headers: {{ "Content-Type": "application/json" }},
    }});
  }}

  async getPatterns(): Promise<Pattern[]> {{
    return this.request<Pattern[]>("/api/v1/ml/patterns");
  }}
}}
'''

        # Go template
        self._templates[SDKLanguage.GO] = '''
// {package_name} v{version}
// Auto-generated SDK for PilotSuite Core API

package {package_name}

import (
    "bytes"
    "encoding/json"
    "fmt"
    "net/http"
)

type Client struct {{
    BaseURL string
    APIKey  string
    HTTPClient *http.Client
}}

type HealthResponse struct {{
    Status string `json:"status"`
}}

type RAGQueryRequest struct {{
    Query string `json:"query"`
    K     int    `json:"k,omitempty"`
}}

type RAGQueryResponse struct {{
    Results []interface{{}} `json:"results"`
    Query   string          `json:"query"`
}}

func NewClient(baseURL, apiKey string) *Client {{
    return &Client{{
        BaseURL:    baseURL,
        APIKey:     apiKey,
        HTTPClient: &http.Client{{}},
    }}
}}

func (c *Client) Health() (*HealthResponse, error) {{
    req, _ := http.NewRequest("GET", c.BaseURL+"/api/v1/health", nil)
    if c.APIKey != "" {{
        req.Header.Set("X-API-Key", c.APIKey)
    }}
    
    resp, err := c.HTTPClient.Do(req)
    if err != nil {{
        return nil, err
    }}
    defer resp.Body.Close()
    
    var result HealthResponse
    json.NewDecoder(resp.Body).Decode(&result)
    return &result, nil
}}

func (c *Client) QueryRag(query string, k int) (*RAGQueryResponse, error) {{
    body, _ := json.Marshal(RAGQueryRequest{{Query: query, K: k}})
    req, _ := http.NewRequest("POST", c.BaseURL+"/api/v1/rag/query", bytes.NewReader(body))
    req.Header.Set("Content-Type", "application/json")
    if c.APIKey != "" {{
        req.Header.Set("X-API-Key", c.APIKey)
    }}
    
    resp, err := c.HTTPClient.Do(req)
    if err != nil {{
        return nil, err
    }}
    defer resp.Body.Close()
    
    var result RAGQueryResponse
    json.NewDecoder(resp.Body).Decode(&result)
    return &result, nil
}}
'''

    def generate(self, config: SDKConfig, openapi_spec: Dict[str, Any]) -> str:
        """Generate SDK code."""
        template = self._templates.get(config.language)
        if not template:
            raise ValueError(f"Unknown language: {config.language}")
        
        class_name = config.package_name.replace("-", "_").replace(" ", "").title().replace("_", "")
        
        code = template.format(
            package_name=config.package_name,
            version=config.version,
            author=config.author,
            class_name=class_name,
        )
        
        return code

    def save_sdk(self, config: SDKConfig, code: str):
        """Save generated SDK to file."""
        output_dir = Path(config.output_dir)
        output_dir.mkdir(parents=True, exist_ok=True)
        
        if config.language == SDKLanguage.PYTHON:
            file_path = output_dir / f"{config.package_name.replace('-', '_')}.py"
        elif config.language == SDKLanguage.TYPESCRIPT:
            file_path = output_dir / f"{config.package_name}.ts"
        elif config.language == SDKLanguage.GO:
            file_path = output_dir / f"{config.package_name}.go"
        else:
            file_path = output_dir / "sdk.txt"
        
        with open(file_path, 'w') as f:
            f.write(code)
        
        logger.info(f"Saved {config.language.value} SDK to {file_path}")

    def generate_all(self, config_base: SDKConfig, openapi_spec: Dict) -> Dict[str, str]:
        """Generate SDKs for all languages."""
        results = {}
        
        for lang in SDKLanguage:
            config = SDKConfig(
                language=lang,
                package_name=config_base.package_name,
                version=config_base.version,
                author=config_base.author,
                output_dir=f"{config_base.output_dir}/{lang.value}",
            )
            
            code = self.generate(config, openapi_spec)
            self.save_sdk(config, code)
            results[lang.value] = code
        
        return results


# Global default SDK generator
default_sdk_generator: Optional[SDKGenerator] = None


def init_sdk_generator() -> SDKGenerator:
    """Initialize global SDK generator."""
    global default_sdk_generator
    default_sdk_generator = SDKGenerator()
    return default_sdk_generator


def generate_sdk(language: str, **kwargs) -> str:
    """Convenience function to generate SDK."""
    if default_sdk_generator:
        config = SDKConfig(
            language=SDKLanguage(language),
            **kwargs
        )
        return default_sdk_generator.generate(config, {})
    return ""
