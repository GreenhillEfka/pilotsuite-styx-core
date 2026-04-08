/**
 * RAG Chat UI Component
 * 
 * Lit-based chat interface for RAG Hybrid Search
 * Features: Chat input, search button, results list with relevance scores,
 * filter options (BM25/Semantic/Hybrid), history, loading states, error handling
 * 
 * @author Clawdya
 * @version 1.0.0
 */

import { LitElement, html } from 'lit';
import { customElement, property, state } from 'lit/decorators.js';
import { classMap } from 'lit/directives/class-map.js';
import { ragChatStyles } from './rag_chat_ui.styles.js';

// Type definitions
export interface RAGSearchResult {
  id: string;
  score: number;
  fused_score?: number;
  lexical_score?: number;
  semantic_score?: number;
  lexical_rank?: number;
  semantic_rank?: number;
  text?: string;
  metadata?: Record<string, unknown>;
}

export interface RAGSearchResponse {
  namespace: string;
  query: string;
  mode: 'hybrid_rrf' | 'bm25' | 'semantic';
  results: RAGSearchResult[];
  warnings: string[];
  took_ms: number;
  query_type?: 'local' | 'web' | 'hybrid';
  sources?: string[];
}

export interface RAGSearchHistoryItem {
  id: string;
  query: string;
  mode: 'hybrid' | 'bm25' | 'semantic';
  timestamp: number;
  resultCount: number;
  useWeb?: boolean;
  queryType?: 'local' | 'web' | 'hybrid';
}

export type SearchMode = 'hybrid' | 'bm25' | 'semantic';

/**
 * RAG Chat UI Component
 * 
 * A chat-style interface for interacting with the RAG Hybrid Search API.
 * Provides search input, mode selection, results display, and search history.
 */
@customElement('rag-chat-ui')
export class RAGChatUI extends LitElement {
  // API Configuration
  @property({ type: String })
  apiBaseUrl = '/api/v1/rag';

  @property({ type: String })
  authToken = '';

  // Search state
  @state()
  private searchQuery = '';

  @state()
  private searchMode: SearchMode = 'hybrid';

  @state()
  private useWeb = false;

  @state()
  private isLoading = false;

  @state()
  private error: string | null = null;

  @state()
  private results: RAGSearchResult[] = [];

  @state()
  private searchHistory: RAGSearchHistoryItem[] = [];

  @state()
  private showHistory = false;

  @state()
  private queryType: 'local' | 'web' | 'hybrid' = 'local';

  @state()
  private sources: string[] = [];

  @state()
  private selectedResult: RAGSearchResult | null = null;

  // Performance metrics
  @state()
  private lastSearchTookMs: number | null = null;

  // Max history items
  private readonly maxHistoryItems = 10;

  static override styles = ragChatStyles;

  override render() {
    return html`
      <div class="container">
        <!-- Header -->
        <div class="header">
          <h2>🧠 RAG Hybrid Search</h2>
          <div class="header-actions">
            <button 
              class="mode-btn" 
              @click=${this._toggleHistory}
              title="Search History"
            >
              📜 History
            </button>
          </div>
        </div>

        <!-- Mode Selector -->
        <div class="mode-selector">
          <button 
            class=${classMap({ 'mode-btn': true, active: this.searchMode === 'bm25' })}
            @click=${() => this._setMode('bm25')}
          >
            BM25
          </button>
          <button 
            class=${classMap({ 'mode-btn': true, active: this.searchMode === 'semantic' })}
            @click=${() => this._setMode('semantic')}
          >
            Semantic
          </button>
          <button 
            class=${classMap({ 'mode-btn': true, active: this.searchMode === 'hybrid' })}
            @click=${() => this._setMode('hybrid')}
          >
            Hybrid
          </button>
        </div>

        <!-- Web Search Toggle -->
        <div class="web-toggle-container">
          <label class="web-toggle">
            <input 
              type="checkbox" 
              ?checked=${this.useWeb}
              @change=${this._handleWebToggle}
              ?disabled=${this.isLoading}
            />
            <span class="toggle-slider"></span>
            <span class="toggle-label">
              Web-Suche (SearXNG)
              <span class="tooltip">Aktiviert Web-Suche bei SearXNG</span>
            </span>
          </label>
          ${this.queryType !== 'local' 
            ? html`
                <span class=${classMap({ 
                  'query-type-badge': true, 
                  'local': this.queryType === 'local',
                  'web': this.queryType === 'web',
                  'hybrid': this.queryType === 'hybrid'
                })}>
                  ${this.queryType === 'local' ? '🟢' : this.queryType === 'web' ? '🔵' : '🟣'}
                  ${this.queryType === 'local' ? 'Lokal' : this.queryType === 'web' ? 'Web' : 'Hybrid'}
                </span>
              ` 
            : ''
          }
        </div>

        <!-- Chat Area -->
        <div class="chat-area">
          ${this._renderChatMessages()}
        </div>

        <!-- Input Area -->
        <div class="input-area">
          <input
            type="text"
            class="search-input"
            placeholder="Ask a question..."
            .value=${this.searchQuery}
            @input=${this._handleInput}
            @keydown=${this._handleKeydown}
            ?disabled=${this.isLoading}
          />
          <button 
            class="search-btn" 
            @click=${this._handleSearch}
            ?disabled=${this.isLoading || !this.searchQuery.trim()}
          >
            ${this.isLoading 
              ? html`<div class="spinner" style="width:18px;height:18px;border-width:2px;"></div>`
              : html`
                  <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                    <circle cx="11" cy="11" r="8"/>
                    <path d="M21 21l-4.35-4.35"/>
                  </svg>
                `
            }
            Search
          </button>
        </div>

        <!-- History Panel -->
        ${this.showHistory ? this._renderHistoryPanel() : null}
      </div>
    `;
  }

  private _renderChatMessages() {
    if (this.isLoading) {
      return html`
        <div class="loading-container">
          <div class="spinner"></div>
          <div class="loading-text">Searching knowledge base...</div>
        </div>
      `;
    }

    if (this.error) {
      return html`
        <div class="error-container">
          ⚠️ ${this.error}
        </div>
      `;
    }

    if (this.results.length === 0 && !this.selectedResult) {
      return html`
        <div class="empty-state">
          <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.5">
            <circle cx="11" cy="11" r="8"/>
            <path d="M21 21l-4.35-4.35"/>
          </svg>
          <h3>Start Your Search</h3>
          <p>Enter a question above and choose your search mode:<br/>
             <strong>BM25</strong> for keyword matching,<br/>
             <strong>Semantic</strong> for meaning-based search,<br/>
             <strong>Hybrid</strong> for best of both worlds.</p>
        </div>
      `;
    }

    return html`
      ${this.results.length > 0 || this.isLoading || this.error
        ? html`
            <div class="chat-message user">
              <div class="message-bubble">
                ${this.results.length > 0 ? this.results[0].text?.substring(0, 100) || this.searchQuery : this.searchQuery}
                <div style="font-size:11px;opacity:0.7;margin-top:4px;">
                  Mode: ${this.searchMode.toUpperCase()} ${this.useWeb ? ' + Web' : ''}
                </div>
              </div>
            </div>
          `
        : ''
      }

      ${this.results.length > 0 
        ? html`
            <div class="chat-message assistant">
              <div class="message-bubble" style="width:100%;max-width:100%;">
                <div class="results-container">
                  <div class="results-header">
                    <span>Found ${this.results.length} result${this.results.length !== 1 ? 's' : ''}</span>
                    ${this.lastSearchTookMs 
                      ? html`<span>⏱️ ${this.lastSearchTookMs.toFixed(0)}ms</span>` 
                      : ''
                    }
                  </div>
                  <div class="results-list">
                    ${this.results.map((result, index) => this._renderResultItem(result, index))}
                  </div>
                  ${this.sources.length > 0 
                    ? html`
                        <div class="sources-section">
                          <strong>📚 Quellen:</strong>
                          <div class="sources-list">
                            ${this.sources.map(source => html`
                              <span class="source-badge">${source}</span>
                            `)}
                          </div>
                        </div>
                      `
                    : ''
                  }
                  ${this.selectedResult 
                    ? this._renderResultDetail(this.selectedResult)
                    : ''
                  }
                </div>
              </div>
            </div>
          `
        : ''
      }
    `;
  }

  private _renderResultItem(result: RAGSearchResult, index: number) {
    const isSelected = this.selectedResult?.id === result.id;
    
    return html`
      <div 
        class=${classMap({ 'result-item': true, selected: isSelected })}
        @click=${() => this._selectResult(result)}
      >
        <div class="result-header">
          <span class="result-id">${result.id}</span>
          <div class="result-score">
            <span class="score-badge">Score: ${result.score.toFixed(3)}</span>
            ${result.lexical_score !== undefined 
              ? html`<span class="score-badge lexical">BM25: ${result.lexical_score.toFixed(3)}</span>` 
              : ''
            }
            ${result.semantic_score !== undefined 
              ? html`<span class="score-badge semantic">Semantic: ${result.semantic_score.toFixed(3)}</span>` 
              : ''
            }
          </div>
        </div>
        ${result.text 
          ? html`<div class="result-text">${result.text}</div>` 
          : ''
        }
        ${result.metadata 
          ? html`
              <div class="result-metadata">
                ${Object.entries(result.metadata).slice(0, 3).map(([key, value]) => 
                  html`${key}: ${String(value)} `
                )}
              </div>
            `
          : ''
        }
      </div>
    `;
  }

  private _renderResultDetail(result: RAGSearchResult) {
    return html`
      <div class="result-detail">
        <h4>📄 Result Details</h4>
        <div class="result-detail-text">
          ${result.text || 'No text content available'}
        </div>
        ${result.metadata 
          ? html`
              <div style="margin-top:12px;font-size:12px;">
                <strong>Metadata:</strong>
                <pre style="margin:4px 0 0 0;padding:8px;background:#f0f0f0;border-radius:4px;overflow-x:auto;">
${JSON.stringify(result.metadata, null, 2)}
                </pre>
              </div>
            `
          : ''
        }
      </div>
    `;
  }

  private _renderHistoryPanel() {
    return html`
      <div class="history-panel">
        <div class="history-header">
          <span>📜 Search History</span>
          <button class="history-close" @click=${this._toggleHistory}>✕</button>
        </div>
        <div class="history-list">
          ${this.searchHistory.length === 0 
            ? html`
                <div style="padding:20px;text-align:center;color:var(--secondary-text-color);font-size:13px;">
                  No search history yet
                </div>
              `
            : this.searchHistory.map(item => html`
                <div 
                  class="history-item"
                  @click=${() => this._loadHistoryItem(item)}
                >
                  <div class="history-query">${item.query}</div>
                  <div class="history-meta">
                    <span>
                      ${item.mode.toUpperCase()} 
                      ${item.useWeb ? ' + Web' : ''}
                      • ${item.resultCount} results
                      ${item.queryType 
                        ? html` • <span class="query-type-badge ${item.queryType}" style="display:inline-flex;padding:2px 6px;font-size:10px;">
                            ${item.queryType === 'local' ? '🟢' : item.queryType === 'web' ? '🔵' : '🟣'}
                            ${item.queryType}
                          </span>`
                        : ''
                      }
                    </span>
                    <span>${this._formatTimeAgo(item.timestamp)}</span>
                  </div>
                </div>
              `)
          }
        </div>
      </div>
    `;
  }

  // Event Handlers
  private _handleInput(e: Event) {
    const target = e.target as HTMLInputElement;
    this.searchQuery = target.value;
  }

  private _handleWebToggle(e: Event) {
    const target = e.target as HTMLInputElement;
    this.useWeb = target.checked;
  }

  private _handleKeydown(e: KeyboardEvent) {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault();
      this._handleSearch();
    }
  }

  private async _handleSearch() {
    const query = this.searchQuery.trim();
    if (!query || this.isLoading) return;

    this.isLoading = true;
    this.error = null;
    this.selectedResult = null;

    try {
      const endpoint = this._getSearchEndpoint();
      const requestBody = this._getSearchRequestBody(query);

      const response = await fetch(`${this.apiBaseUrl}${endpoint}`, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          ...(this.authToken ? { 'Authorization': `Bearer ${this.authToken}` } : {}),
        },
        body: JSON.stringify(requestBody),
      });

      if (!response.ok) {
        const errorData = await response.json().catch(() => ({}));
        throw new Error(errorData.error || `HTTP ${response.status}`);
      }

      const data: RAGSearchResponse = await response.json();
      
      this.results = data.results;
      this.lastSearchTookMs = data.took_ms;
      this.queryType = data.query_type || (this.useWeb ? 'hybrid' : 'local');
      this.sources = data.sources || [];
      
      // Add to history
      this._addToHistory(query, this.searchMode, data.results.length);
      
      // Clear input
      this.searchQuery = '';
      
    } catch (err) {
      this.error = err instanceof Error ? err.message : 'Search failed';
      console.error('RAG search error:', err);
    } finally {
      this.isLoading = false;
    }
  }

  private _getSearchEndpoint(): string {
    switch (this.searchMode) {
      case 'bm25':
        return '/search';
      case 'semantic':
        return '/search';
      case 'hybrid':
      default:
        return '/search';
    }
  }

  private _getSearchRequestBody(query: string): Record<string, unknown> {
    const baseBody = {
      query,
      top_k: 10,
      include_text: true,
      include_metadata: true,
      use_web: this.useWeb,
    };

    switch (this.searchMode) {
      case 'bm25':
        return {
          ...baseBody,
          use_lexical: true,
          use_semantic: false,
        };
      case 'semantic':
        return {
          ...baseBody,
          use_lexical: false,
          use_semantic: true,
        };
      case 'hybrid':
      default:
        return {
          ...baseBody,
          use_lexical: true,
          use_semantic: true,
        };
    }
  }

  private _setMode(mode: SearchMode) {
    this.searchMode = mode;
  }

  private _selectResult(result: RAGSearchResult) {
    this.selectedResult = result;
  }

  private _toggleHistory() {
    this.showHistory = !this.showHistory;
  }

  private _addToHistory(query: string, mode: SearchMode, resultCount: number) {
    const newItem: RAGSearchHistoryItem = {
      id: Date.now().toString(),
      query,
      mode,
      timestamp: Date.now(),
      resultCount,
      useWeb: this.useWeb,
      queryType: this.queryType,
    };

    this.searchHistory = [newItem, ...this.searchHistory].slice(0, this.maxHistoryItems);
  }

  private _loadHistoryItem(item: RAGSearchHistoryItem) {
    this.searchQuery = item.query;
    this.searchMode = item.mode;
    this.useWeb = item.useWeb || false;
    this.showHistory = false;
    this._handleSearch();
  }

  private _formatTimeAgo(timestamp: number): string {
    const seconds = Math.floor((Date.now() - timestamp) / 1000);
    
    if (seconds < 60) return 'Just now';
    if (seconds < 3600) return `${Math.floor(seconds / 60)}m ago`;
    if (seconds < 86400) return `${Math.floor(seconds / 3600)}h ago`;
    return `${Math.floor(seconds / 86400)}d ago`;
  }

  // Public API
  public async search(query: string, mode?: SearchMode): Promise<RAGSearchResult[]> {
    if (mode) this.searchMode = mode;
    this.searchQuery = query;
    await this._handleSearch();
    return this.results;
  }

  public clearHistory(): void {
    this.searchHistory = [];
  }

  public getHistory(): RAGSearchHistoryItem[] {
    return [...this.searchHistory];
  }
}

declare global {
  interface HTMLElementTagNameMap {
    'rag-chat-ui': RAGChatUI;
  }
}
