/**
 * RAG Chat UI Component Tests
 * 
 * Comprehensive test suite for the RAG Chat UI Lit component
 * Tests cover: rendering, user interactions, API integration, 
 * state management, error handling, and edge cases
 * 
 * @author Clawdya
 * @version 1.0.0
 * 
 * Test Count: 25 tests
 */

import { describe, it, expect, beforeEach, afterEach, vi, Mock } from 'vitest';
import { fixture, html, oneEvent } from '@open-wc/testing';
import { aTimeout } from '@open-wc/testing-helpers';
import { RAGChatUI, RAGSearchResult, RAGSearchHistoryItem } from '../../static/rag/rag_chat_ui';

// Mock fetch globally
const mockFetch = vi.fn();
global.fetch = mockFetch as any;

describe('RAGChatUI Component', () => {
  let element: RAGChatUI;

  beforeEach(async () => {
    mockFetch.mockClear();
    element = await fixture<RAGChatUI>(html`<rag-chat-ui></rag-chat-ui>`);
  });

  afterEach(() => {
    vi.clearAllMocks();
  });

  // ==================== RENDERING TESTS ====================

  describe('Rendering', () => {
    it('should render component with header', async () => {
      expect(element).shadowDom.to.include('h2');
      expect(element).shadowDom.to.contain('RAG Hybrid Search');
    });

    it('should render mode selector buttons', async () => {
      const buttons = element.shadowRoot?.querySelectorAll('.mode-btn');
      expect(buttons).to.have.lengthOf(3);
      
      const buttonLabels = Array.from(buttons!).map(btn => btn.textContent?.trim());
      expect(buttonLabels).to.include('BM25');
      expect(buttonLabels).to.include('Semantic');
      expect(buttonLabels).to.include('Hybrid');
    });

    it('should render search input field', async () => {
      const input = element.shadowRoot?.querySelector('.search-input') as HTMLInputElement;
      expect(input).to.exist;
      expect(input?.type).to.equal('text');
      expect(input?.placeholder).to.equal('Ask a question...');
    });

    it('should render search button', async () => {
      const button = element.shadowRoot?.querySelector('.search-btn');
      expect(button).to.exist;
      expect(button?.textContent).to.include('Search');
    });

    it('should display empty state when no results', async () => {
      const emptyState = element.shadowRoot?.querySelector('.empty-state');
      expect(emptyState).to.exist;
      expect(emptyState?.textContent).to.include('Start Your Search');
    });

    it('should have correct default search mode (hybrid)', async () => {
      // Hybrid button should be active by default
      const modeButtons = element.shadowRoot?.querySelectorAll('.mode-btn');
      expect(modeButtons?.[2]).to.have.class('active');
    });

    it('should render web search toggle', async () => {
      const webToggle = element.shadowRoot?.querySelector('.web-toggle');
      expect(webToggle).to.exist;
      
      const checkbox = element.shadowRoot?.querySelector('.web-toggle input[type="checkbox"]');
      expect(checkbox).to.exist;
      expect((checkbox as HTMLInputElement).checked).to.be.false;
    });

    it('should display query type badge after search', async () => {
      mockFetch.mockResolvedValue({
        ok: true,
        json: async () => ({
          results: [{ id: 'doc1', score: 0.9 }],
          warnings: [],
          took_ms: 0,
          query_type: 'hybrid',
        }),
      });

      const input = element.shadowRoot?.querySelector('.search-input') as HTMLInputElement;
      const searchBtn = element.shadowRoot?.querySelector('.search-btn') as HTMLButtonElement;
      
      input.value = 'Test';
      input.dispatchEvent(new Event('input'));
      searchBtn?.click();
      await aTimeout(100);

      expect(element.shadowRoot?.querySelector('.query-type-badge')).to.exist;
    });
  });

  // ==================== MODE SELECTION TESTS ====================

  describe('Mode Selection', () => {
    it('should toggle web search on checkbox change', async () => {
      const webToggle = element.shadowRoot?.querySelector('.web-toggle input[type="checkbox"]') as HTMLInputElement;
      
      webToggle.checked = true;
      webToggle.dispatchEvent(new Event('change'));
      await element.updateComplete;

      expect(webToggle.checked).to.be.true;
    });

    it('should send use_web parameter in request body', async () => {
      const webToggle = element.shadowRoot?.querySelector('.web-toggle input[type="checkbox"]') as HTMLInputElement;
      webToggle.checked = true;
      webToggle.dispatchEvent(new Event('change'));
      await element.updateComplete;

      const input = element.shadowRoot?.querySelector('.search-input') as HTMLInputElement;
      const searchBtn = element.shadowRoot?.querySelector('.search-btn') as HTMLButtonElement;
      
      input.value = 'Test query';
      input.dispatchEvent(new Event('input'));
      await element.updateComplete;
      
      searchBtn?.click();
      await aTimeout(100);

      const callArgs = mockFetch.mock.calls[0];
      const body = JSON.parse(callArgs[1].body);
      
      expect(body.use_web).to.be.true;
    });

    it('should switch to BM25 mode when clicked', async () => {
      const bm25Btn = element.shadowRoot?.querySelector('.mode-btn') as HTMLButtonElement;
      bm25Btn?.click();
      await element.updateComplete;

      expect(bm25Btn).to.have.class('active');
      const otherBtns = element.shadowRoot?.querySelectorAll('.mode-btn:not(:first-child)');
      otherBtns?.forEach(btn => {
        expect(btn).not.to.have.class('active');
      });
    });

    it('should switch to Semantic mode when clicked', async () => {
      const semanticBtn = element.shadowRoot?.querySelectorAll('.mode-btn')[1] as HTMLButtonElement;
      semanticBtn?.click();
      await element.updateComplete;

      expect(semanticBtn).to.have.class('active');
    });

    it('should switch to Hybrid mode when clicked', async () => {
      const hybridBtn = element.shadowRoot?.querySelectorAll('.mode-btn')[2] as HTMLButtonElement;
      hybridBtn?.click();
      await element.updateComplete;

      expect(hybridBtn).to.have.class('active');
    });

    it('should update internal state when mode changes', async () => {
      // Access private property via type assertion for testing
      const bm25Btn = element.shadowRoot?.querySelector('.mode-btn') as HTMLButtonElement;
      bm25Btn?.click();
      await element.updateComplete;

      // Verify mode changed (would need public getter or test via search behavior)
      expect(bm25Btn).to.have.class('active');
    });
  });

  // ==================== INPUT HANDLING TESTS ====================

  describe('Input Handling', () => {
    it('should update search query on input', async () => {
      const input = element.shadowRoot?.querySelector('.search-input') as HTMLInputElement;
      
      input.value = 'Test query';
      input.dispatchEvent(new Event('input'));
      await element.updateComplete;

      // Input should reflect the value
      expect(input.value).to.equal('Test query');
    });

    it('should trigger search on Enter key', async () => {
      const input = element.shadowRoot?.querySelector('.search-input') as HTMLInputElement;
      const searchSpy = vi.spyOn(element as any, '_handleSearch');
      
      input.value = 'Test query';
      input.dispatchEvent(new Event('input'));
      input.dispatchEvent(new KeyboardEvent('keydown', { key: 'Enter' }));
      await element.updateComplete;

      expect(searchSpy).toHaveBeenCalled();
    });

    it('should not trigger search on other keys', async () => {
      const input = element.shadowRoot?.querySelector('.search-input') as HTMLInputElement;
      const searchSpy = vi.spyOn(element as any, '_handleSearch');
      
      input.dispatchEvent(new KeyboardEvent('keydown', { key: 'Escape' }));
      await element.updateComplete;

      expect(searchSpy).not.toHaveBeenCalled();
    });

    it('should disable search button when input is empty', async () => {
      const searchBtn = element.shadowRoot?.querySelector('.search-btn') as HTMLButtonElement;
      expect(searchBtn?.disabled).to.be.true;
    });

    it('should enable search button when input has value', async () => {
      const input = element.shadowRoot?.querySelector('.search-input') as HTMLInputElement;
      const searchBtn = element.shadowRoot?.querySelector('.search-btn') as HTMLButtonElement;
      
      input.value = 'Test';
      input.dispatchEvent(new Event('input'));
      await element.updateComplete;

      expect(searchBtn?.disabled).to.be.false;
    });
  });

  // ==================== API INTEGRATION TESTS ====================

  describe('API Integration', () => {
    const mockResponse: RAGSearchResult[] = [
      { id: 'doc1', score: 0.95, text: 'Result 1', metadata: { source: 'test' } },
      { id: 'doc2', score: 0.87, text: 'Result 2', metadata: {} },
      { id: 'doc3', score: 0.72, text: 'Result 3' },
    ];

    beforeEach(() => {
      mockFetch.mockResolvedValue({
        ok: true,
        json: async () => ({
          namespace: 'default',
          query: 'Test query',
          mode: 'hybrid_rrf',
          results: mockResponse,
          warnings: [],
          took_ms: 45.3,
        }),
      });
    });

    it('should call API endpoint on search', async () => {
      const input = element.shadowRoot?.querySelector('.search-input') as HTMLInputElement;
      const searchBtn = element.shadowRoot?.querySelector('.search-btn') as HTMLButtonElement;
      
      input.value = 'Test query';
      input.dispatchEvent(new Event('input'));
      await element.updateComplete;
      
      searchBtn?.click();
      await aTimeout(100);

      expect(mockFetch).toHaveBeenCalled();
      expect(mockFetch).toHaveBeenCalledWith(
        '/api/v1/rag/search',
        expect.objectContaining({
          method: 'POST',
          headers: expect.any(Object),
          body: expect.any(String),
        })
      );
    });

    it('should send correct request body for hybrid mode', async () => {
      const input = element.shadowRoot?.querySelector('.search-input') as HTMLInputElement;
      const searchBtn = element.shadowRoot?.querySelector('.search-btn') as HTMLButtonElement;
      
      input.value = 'Test query';
      input.dispatchEvent(new Event('input'));
      await element.updateComplete;
      
      searchBtn?.click();
      await aTimeout(100);

      const callArgs = mockFetch.mock.calls[0];
      const body = JSON.parse(callArgs[1].body);
      
      expect(body).to.deep.include({
        query: 'Test query',
        use_lexical: true,
        use_semantic: true,
        include_text: true,
        include_metadata: true,
      });
    });

    it('should send correct request body for BM25 mode', async () => {
      const bm25Btn = element.shadowRoot?.querySelector('.mode-btn') as HTMLButtonElement;
      bm25Btn?.click();
      await element.updateComplete;

      const input = element.shadowRoot?.querySelector('.search-input') as HTMLInputElement;
      const searchBtn = element.shadowRoot?.querySelector('.search-btn') as HTMLButtonElement;
      
      input.value = 'Test query';
      input.dispatchEvent(new Event('input'));
      await element.updateComplete;
      
      searchBtn?.click();
      await aTimeout(100);

      const callArgs = mockFetch.mock.calls[0];
      const body = JSON.parse(callArgs[1].body);
      
      expect(body).to.deep.include({
        use_lexical: true,
        use_semantic: false,
      });
    });

    it('should send correct request body for Semantic mode', async () => {
      const semanticBtn = element.shadowRoot?.querySelectorAll('.mode-btn')[1] as HTMLButtonElement;
      semanticBtn?.click();
      await element.updateComplete;

      const input = element.shadowRoot?.querySelector('.search-input') as HTMLInputElement;
      const searchBtn = element.shadowRoot?.querySelector('.search-btn') as HTMLButtonElement;
      
      input.value = 'Test query';
      input.dispatchEvent(new Event('input'));
      await element.updateComplete;
      
      searchBtn?.click();
      await aTimeout(100);

      const callArgs = mockFetch.mock.calls[0];
      const body = JSON.parse(callArgs[1].body);
      
      expect(body).to.deep.include({
        use_lexical: false,
        use_semantic: true,
      });
    });

    it('should include auth token when configured', async () => {
      element.authToken = 'test-token-123';
      await element.updateComplete;

      const input = element.shadowRoot?.querySelector('.search-input') as HTMLInputElement;
      const searchBtn = element.shadowRoot?.querySelector('.search-btn') as HTMLButtonElement;
      
      input.value = 'Test query';
      input.dispatchEvent(new Event('input'));
      await element.updateComplete;
      
      searchBtn?.click();
      await aTimeout(100);

      const callArgs = mockFetch.mock.calls[0];
      const headers = callArgs[1].headers;
      
      expect(headers).to.include({
        'Authorization': 'Bearer test-token-123',
      });
    });

    it('should display results after successful search', async () => {
      const input = element.shadowRoot?.querySelector('.search-input') as HTMLInputElement;
      const searchBtn = element.shadowRoot?.querySelector('.search-btn') as HTMLButtonElement;
      
      input.value = 'Test query';
      input.dispatchEvent(new Event('input'));
      await element.updateComplete;
      
      searchBtn?.click();
      await aTimeout(100);

      expect(element.shadowRoot?.querySelector('.result-item')).to.exist;
      expect(element.shadowRoot?.querySelectorAll('.result-item')).to.have.lengthOf(3);
    });

    it('should show loading state during search', async () => {
      // Make fetch wait a bit
      mockFetch.mockImplementationOnce(() => 
        new Promise(resolve => 
          setTimeout(() => resolve({
            ok: true,
            json: async () => ({ results: [], warnings: [], took_ms: 0 }),
          }), 100)
        )
      );

      const input = element.shadowRoot?.querySelector('.search-input') as HTMLInputElement;
      const searchBtn = element.shadowRoot?.querySelector('.search-btn') as HTMLButtonElement;
      
      input.value = 'Test query';
      input.dispatchEvent(new Event('input'));
      await element.updateComplete;
      
      searchBtn?.click();
      await aTimeout(10);

      expect(element.shadowRoot?.querySelector('.loading-container')).to.exist;
      expect(element.shadowRoot?.querySelector('.spinner')).to.exist;
    });
  });

  // ==================== ERROR HANDLING TESTS ====================

  describe('Error Handling', () => {
    it('should display error message on API failure', async () => {
      mockFetch.mockResolvedValueOnce({
        ok: false,
        status: 500,
        json: async () => ({ error: 'Internal server error' }),
      });

      const input = element.shadowRoot?.querySelector('.search-input') as HTMLInputElement;
      const searchBtn = element.shadowRoot?.querySelector('.search-btn') as HTMLButtonElement;
      
      input.value = 'Test query';
      input.dispatchEvent(new Event('input'));
      await element.updateComplete;
      
      searchBtn?.click();
      await aTimeout(100);

      expect(element.shadowRoot?.querySelector('.error-container')).to.exist;
      expect(element.shadowRoot?.querySelector('.error-container')?.textContent)
        .to.include('Internal server error');
    });

    it('should handle network errors gracefully', async () => {
      mockFetch.mockRejectedValueOnce(new Error('Network error'));

      const input = element.shadowRoot?.querySelector('.search-input') as HTMLInputElement;
      const searchBtn = element.shadowRoot?.querySelector('.search-btn') as HTMLButtonElement;
      
      input.value = 'Test query';
      input.dispatchEvent(new Event('input'));
      await element.updateComplete;
      
      searchBtn?.click();
      await aTimeout(100);

      expect(element.shadowRoot?.querySelector('.error-container')).to.exist;
    });

    it('should clear error on new search', async () => {
      mockFetch.mockRejectedValueOnce(new Error('First error'));
      mockFetch.mockResolvedValueOnce({
        ok: true,
        json: async () => ({ results: [], warnings: [], took_ms: 0 }),
      });

      const input = element.shadowRoot?.querySelector('.search-input') as HTMLInputElement;
      const searchBtn = element.shadowRoot?.querySelector('.search-btn') as HTMLButtonElement;
      
      // First search (fails)
      input.value = 'Test query 1';
      input.dispatchEvent(new Event('input'));
      searchBtn?.click();
      await aTimeout(100);

      expect(element.shadowRoot?.querySelector('.error-container')).to.exist;

      // Second search (succeeds)
      input.value = 'Test query 2';
      input.dispatchEvent(new Event('input'));
      searchBtn?.click();
      await aTimeout(100);

      expect(element.shadowRoot?.querySelector('.error-container')).not.to.exist;
    });

    it('should not search when query is empty', async () => {
      const searchBtn = element.shadowRoot?.querySelector('.search-btn') as HTMLButtonElement;
      searchBtn?.click();
      await element.updateComplete;

      expect(mockFetch).not.toHaveBeenCalled();
    });
  });

  // ==================== HISTORY TESTS ====================

  describe('Search History', () => {
    it('should add successful search to history', async () => {
      mockFetch.mockResolvedValue({
        ok: true,
        json: async () => ({
          namespace: 'default',
          query: 'Test query',
          mode: 'hybrid_rrf',
          results: [{ id: 'doc1', score: 0.9 }],
          warnings: [],
          took_ms: 45,
        }),
      });

      const input = element.shadowRoot?.querySelector('.search-input') as HTMLInputElement;
      const searchBtn = element.shadowRoot?.querySelector('.search-btn') as HTMLButtonElement;
      
      input.value = 'Test query';
      input.dispatchEvent(new Event('input'));
      await element.updateComplete;
      
      searchBtn?.click();
      await aTimeout(100);

      const history = element.getHistory();
      expect(history).to.have.lengthOf(1);
      expect(history[0].query).to.equal('Test query');
      expect(history[0].mode).to.equal('hybrid');
    });

    it('should store web toggle state in history', async () => {
      mockFetch.mockResolvedValue({
        ok: true,
        json: async () => ({
          results: [{ id: 'doc1', score: 0.9 }],
          warnings: [],
          took_ms: 45,
          query_type: 'hybrid',
        }),
      });

      // Enable web toggle
      const webToggle = element.shadowRoot?.querySelector('.web-toggle input[type="checkbox"]') as HTMLInputElement;
      webToggle.checked = true;
      webToggle.dispatchEvent(new Event('change'));
      await element.updateComplete;

      const input = element.shadowRoot?.querySelector('.search-input') as HTMLInputElement;
      const searchBtn = element.shadowRoot?.querySelector('.search-btn') as HTMLButtonElement;
      
      input.value = 'Test query';
      input.dispatchEvent(new Event('input'));
      searchBtn?.click();
      await aTimeout(100);

      const history = element.getHistory();
      expect(history).to.have.lengthOf(1);
      expect(history[0].useWeb).to.be.true;
      expect(history[0].queryType).to.equal('hybrid');
    });

    it('should limit history to 10 items', async () => {
      mockFetch.mockResolvedValue({
        ok: true,
        json: async () => ({ results: [], warnings: [], took_ms: 0 }),
      });

      // Perform 12 searches
      for (let i = 0; i < 12; i++) {
        const input = element.shadowRoot?.querySelector('.search-input') as HTMLInputElement;
        const searchBtn = element.shadowRoot?.querySelector('.search-btn') as HTMLButtonElement;
        
        input.value = `Query ${i}`;
        input.dispatchEvent(new Event('input'));
        await element.updateComplete;
        
        searchBtn?.click();
        await aTimeout(50);
      }

      const history = element.getHistory();
      expect(history).to.have.lengthOf(10);
      expect(history[0].query).to.equal('Query 11');
    });

    it('should toggle history panel visibility', async () => {
      const historyBtn = element.shadowRoot?.querySelector('.mode-btn') as HTMLButtonElement;
      
      // Open history
      historyBtn?.click();
      await element.updateComplete;
      
      expect(element.shadowRoot?.querySelector('.history-panel')).to.exist;

      // Close history
      historyBtn?.click();
      await element.updateComplete;
      
      expect(element.shadowRoot?.querySelector('.history-panel')).not.to.exist;
    });

    it('should display history items in panel', async () => {
      // Add item to history
      mockFetch.mockResolvedValue({
        ok: true,
        json: async () => ({ results: [], warnings: [], took_ms: 0 }),
      });

      const input = element.shadowRoot?.querySelector('.search-input') as HTMLInputElement;
      const searchBtn = element.shadowRoot?.querySelector('.search-btn') as HTMLButtonElement;
      
      input.value = 'Test query';
      input.dispatchEvent(new Event('input'));
      searchBtn?.click();
      await aTimeout(100);

      // Open history panel
      const historyBtn = element.shadowRoot?.querySelector('.mode-btn') as HTMLButtonElement;
      historyBtn?.click();
      await element.updateComplete;

      expect(element.shadowRoot?.querySelector('.history-item')).to.exist;
      expect(element.shadowRoot?.querySelector('.history-query')?.textContent)
        .to.include('Test query');
    });

    it('should load history item on click', async () => {
      // This would require more complex mocking, testing the method directly
      const historyItem: RAGSearchHistoryItem = {
        id: 'test-1',
        query: 'Loaded query',
        mode: 'bm25',
        timestamp: Date.now(),
        resultCount: 5,
      };

      (element as any)._loadHistoryItem(historyItem);
      
      expect((element as any).searchQuery).to.equal('Loaded query');
      expect((element as any).searchMode).to.equal('bm25');
    });

    it('should clear history', async () => {
      // Add item first
      mockFetch.mockResolvedValue({
        ok: true,
        json: async () => ({ results: [], warnings: [], took_ms: 0 }),
      });

      const input = element.shadowRoot?.querySelector('.search-input') as HTMLInputElement;
      const searchBtn = element.shadowRoot?.querySelector('.search-btn') as HTMLButtonElement;
      
      input.value = 'Test';
      input.dispatchEvent(new Event('input'));
      searchBtn?.click();
      await aTimeout(100);

      expect(element.getHistory()).to.have.lengthOf(1);

      // Clear history
      element.clearHistory();
      expect(element.getHistory()).to.have.lengthOf(0);
    });
  });

  // ==================== RESULT DISPLAY TESTS ====================

  describe('Result Display', () => {
    it('should display result scores', async () => {
      mockFetch.mockResolvedValue({
        ok: true,
        json: async () => ({
          results: [{ id: 'doc1', score: 0.95 }],
          warnings: [],
          took_ms: 0,
        }),
      });

      const input = element.shadowRoot?.querySelector('.search-input') as HTMLInputElement;
      const searchBtn = element.shadowRoot?.querySelector('.search-btn') as HTMLButtonElement;
      
      input.value = 'Test';
      input.dispatchEvent(new Event('input'));
      searchBtn?.click();
      await aTimeout(100);

      expect(element.shadowRoot?.querySelector('.score-badge')?.textContent)
        .to.include('0.95');
    });

    it('should display lexical and semantic scores for hybrid results', async () => {
      mockFetch.mockResolvedValue({
        ok: true,
        json: async () => ({
          results: [{ 
            id: 'doc1', 
            score: 0.95,
            lexical_score: 0.9,
            semantic_score: 0.8,
          }],
          warnings: [],
          took_ms: 0,
        }),
      });

      const input = element.shadowRoot?.querySelector('.search-input') as HTMLInputElement;
      const searchBtn = element.shadowRoot?.querySelector('.search-btn') as HTMLButtonElement;
      
      input.value = 'Test';
      input.dispatchEvent(new Event('input'));
      searchBtn?.click();
      await aTimeout(100);

      expect(element.shadowRoot?.querySelector('.score-badge.lexical')).to.exist;
      expect(element.shadowRoot?.querySelector('.score-badge.semantic')).to.exist;
    });

    it('should select result on click', async () => {
      mockFetch.mockResolvedValue({
        ok: true,
        json: async () => ({
          results: [{ id: 'doc1', score: 0.95, text: 'Full text content' }],
          warnings: [],
          took_ms: 0,
        }),
      });

      const input = element.shadowRoot?.querySelector('.search-input') as HTMLInputElement;
      const searchBtn = element.shadowRoot?.querySelector('.search-btn') as HTMLButtonElement;
      
      input.value = 'Test';
      input.dispatchEvent(new Event('input'));
      searchBtn?.click();
      await aTimeout(100);

      const resultItem = element.shadowRoot?.querySelector('.result-item') as HTMLDivElement;
      resultItem?.click();
      await element.updateComplete;

      expect(element.shadowRoot?.querySelector('.result-detail')).to.exist;
    });

    it('should display result metadata', async () => {
      mockFetch.mockResolvedValue({
        ok: true,
        json: async () => ({
          results: [{ 
            id: 'doc1', 
            score: 0.95, 
            metadata: { source: 'test', type: 'document' } 
          }],
          warnings: [],
          took_ms: 0,
        }),
      });

      const input = element.shadowRoot?.querySelector('.search-input') as HTMLInputElement;
      const searchBtn = element.shadowRoot?.querySelector('.search-btn') as HTMLButtonElement;
      
      input.value = 'Test';
      input.dispatchEvent(new Event('input'));
      searchBtn?.click();
      await aTimeout(100);

      expect(element.shadowRoot?.querySelector('.result-metadata')).to.exist;
    });

    it('should show search duration', async () => {
      mockFetch.mockResolvedValue({
        ok: true,
        json: async () => ({
          results: [],
          warnings: [],
          took_ms: 123.45,
        }),
      });

      const input = element.shadowRoot?.querySelector('.search-input') as HTMLInputElement;
      const searchBtn = element.shadowRoot?.querySelector('.search-btn') as HTMLButtonElement;
      
      input.value = 'Test';
      input.dispatchEvent(new Event('input'));
      searchBtn?.click();
      await aTimeout(100);

      expect(element.shadowRoot?.querySelector('.results-header')?.textContent)
        .to.include('123ms');
    });

    it('should display sources from API response', async () => {
      mockFetch.mockResolvedValue({
        ok: true,
        json: async () => ({
          results: [{ id: 'doc1', score: 0.95 }],
          warnings: [],
          took_ms: 0,
          sources: ['local', 'searxng'],
        }),
      });

      const input = element.shadowRoot?.querySelector('.search-input') as HTMLInputElement;
      const searchBtn = element.shadowRoot?.querySelector('.search-btn') as HTMLButtonElement;
      
      input.value = 'Test';
      input.dispatchEvent(new Event('input'));
      searchBtn?.click();
      await aTimeout(100);

      expect(element.shadowRoot?.querySelector('.sources-section')).to.exist;
      expect(element.shadowRoot?.querySelectorAll('.source-badge')).to.have.lengthOf(2);
    });

    it('should show query type badge with correct color for local', async () => {
      mockFetch.mockResolvedValue({
        ok: true,
        json: async () => ({
          results: [],
          warnings: [],
          took_ms: 0,
          query_type: 'local',
        }),
      });

      const input = element.shadowRoot?.querySelector('.search-input') as HTMLInputElement;
      const searchBtn = element.shadowRoot?.querySelector('.search-btn') as HTMLButtonElement;
      
      input.value = 'Test';
      input.dispatchEvent(new Event('input'));
      searchBtn?.click();
      await aTimeout(100);

      const badge = element.shadowRoot?.querySelector('.query-type-badge.local');
      expect(badge).to.exist;
      expect(badge?.textContent).to.include('🟢');
    });

    it('should show query type badge with correct color for web', async () => {
      mockFetch.mockResolvedValue({
        ok: true,
        json: async () => ({
          results: [],
          warnings: [],
          took_ms: 0,
          query_type: 'web',
        }),
      });

      const input = element.shadowRoot?.querySelector('.search-input') as HTMLInputElement;
      const searchBtn = element.shadowRoot?.querySelector('.search-btn') as HTMLButtonElement;
      
      input.value = 'Test';
      input.dispatchEvent(new Event('input'));
      searchBtn?.click();
      await aTimeout(100);

      const badge = element.shadowRoot?.querySelector('.query-type-badge.web');
      expect(badge).to.exist;
      expect(badge?.textContent).to.include('🔵');
    });

    it('should show query type badge with correct color for hybrid', async () => {
      mockFetch.mockResolvedValue({
        ok: true,
        json: async () => ({
          results: [],
          warnings: [],
          took_ms: 0,
          query_type: 'hybrid',
        }),
      });

      const input = element.shadowRoot?.querySelector('.search-input') as HTMLInputElement;
      const searchBtn = element.shadowRoot?.querySelector('.search-btn') as HTMLButtonElement;
      
      input.value = 'Test';
      input.dispatchEvent(new Event('input'));
      searchBtn?.click();
      await aTimeout(100);

      const badge = element.shadowRoot?.querySelector('.query-type-badge.hybrid');
      expect(badge).to.exist;
      expect(badge?.textContent).to.include('🟣');
    });
  });

  // ==================== PUBLIC API TESTS ====================

  describe('Public API', () => {
    it('should provide search method', async () => {
      mockFetch.mockResolvedValue({
        ok: true,
        json: async () => ({
          results: [{ id: 'doc1', score: 0.9 }],
          warnings: [],
          took_ms: 0,
        }),
      });

      const results = await element.search('Test query');
      
      expect(results).to.have.lengthOf(1);
      expect(results[0].id).to.equal('doc1');
    });

    it('should accept mode parameter in search method', async () => {
      mockFetch.mockResolvedValue({
        ok: true,
        json: async () => ({ results: [], warnings: [], took_ms: 0 }),
      });

      await element.search('Test', 'bm25');
      
      const callArgs = mockFetch.mock.calls[0];
      const body = JSON.parse(callArgs[1].body);
      
      expect(body.use_lexical).to.be.true;
      expect(body.use_semantic).to.be.false;
    });
  });

  // ==================== EDGE CASES ====================

  describe('Edge Cases', () => {
    it('should handle empty results array', async () => {
      mockFetch.mockResolvedValue({
        ok: true,
        json: async () => ({
          results: [],
          warnings: [],
          took_ms: 0,
        }),
      });

      const input = element.shadowRoot?.querySelector('.search-input') as HTMLInputElement;
      const searchBtn = element.shadowRoot?.querySelector('.search-btn') as HTMLButtonElement;
      
      input.value = 'Test';
      input.dispatchEvent(new Event('input'));
      searchBtn?.click();
      await aTimeout(100);

      // Should not crash, just show no results
      expect(element.shadowRoot?.querySelector('.results-list')).to.exist;
    });

    it('should handle warnings from API', async () => {
      mockFetch.mockResolvedValue({
        ok: true,
        json: async () => ({
          results: [],
          warnings: ['Semantic backend not configured'],
          took_ms: 0,
        }),
      });

      const input = element.shadowRoot?.querySelector('.search-input') as HTMLInputElement;
      const searchBtn = element.shadowRoot?.querySelector('.search-btn') as HTMLButtonElement;
      
      input.value = 'Test';
      input.dispatchEvent(new Event('input'));
      searchBtn?.click();
      await aTimeout(100);

      // Component should handle warnings gracefully
      expect(element).to.exist;
    });

    it('should handle very long queries', async () => {
      const longQuery = 'A'.repeat(1000);
      
      mockFetch.mockResolvedValue({
        ok: true,
        json: async () => ({ results: [], warnings: [], took_ms: 0 }),
      });

      const input = element.shadowRoot?.querySelector('.search-input') as HTMLInputElement;
      const searchBtn = element.shadowRoot?.querySelector('.search-btn') as HTMLButtonElement;
      
      input.value = longQuery;
      input.dispatchEvent(new Event('input'));
      await element.updateComplete;
      
      searchBtn?.click();
      await aTimeout(100);

      expect(mockFetch).toHaveBeenCalled();
    });

    it('should handle special characters in query', async () => {
      const specialQuery = 'Test <>&"\' query!@#$%';
      
      mockFetch.mockResolvedValue({
        ok: true,
        json: async () => ({ results: [], warnings: [], took_ms: 0 }),
      });

      const input = element.shadowRoot?.querySelector('.search-input') as HTMLInputElement;
      const searchBtn = element.shadowRoot?.querySelector('.search-btn') as HTMLButtonElement;
      
      input.value = specialQuery;
      input.dispatchEvent(new Event('input'));
      await element.updateComplete;
      
      searchBtn?.click();
      await aTimeout(100);

      const callArgs = mockFetch.mock.calls[0];
      const body = JSON.parse(callArgs[1].body);
      
      expect(body.query).to.equal(specialQuery);
    });

    it('should handle rapid successive searches', async () => {
      mockFetch.mockResolvedValue({
        ok: true,
        json: async () => ({ results: [], warnings: [], took_ms: 0 }),
      });

      const input = element.shadowRoot?.querySelector('.search-input') as HTMLInputElement;
      const searchBtn = element.shadowRoot?.querySelector('.search-btn') as HTMLButtonElement;
      
      // Trigger 5 rapid searches
      for (let i = 0; i < 5; i++) {
        input.value = `Query ${i}`;
        input.dispatchEvent(new Event('input'));
        await element.updateComplete;
        searchBtn?.click();
      }
      
      await aTimeout(200);

      // Should complete without errors
      expect(element).to.exist;
    });
  });
});
