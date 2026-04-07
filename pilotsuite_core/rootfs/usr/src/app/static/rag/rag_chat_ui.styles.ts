/**
 * RAG Chat UI Styles
 * 
 * Home Assistant Design System compatible styles
 * for the RAG Chat UI component
 * 
 * @author Clawdya
 * @version 1.0.0
 */

import { css } from 'lit';

export const ragChatStyles = css`
  :host {
    display: block;
    font-family: var(--ha-font-family, 'Roboto', sans-serif);
    color: var(--primary-text-color, #212121);
    background: var(--card-background-color, #ffffff);
    border-radius: var(--ha-card-border-radius, 8px);
    box-shadow: var(--ha-card-box-shadow, 0 2px 4px rgba(0,0,0,0.1));
    overflow: hidden;
  }

  .container {
    display: flex;
    flex-direction: column;
    height: 600px;
    max-height: 80vh;
  }

  /* Header */
  .header {
    display: flex;
    justify-content: space-between;
    align-items: center;
    padding: 16px 20px;
    border-bottom: 1px solid var(--divider-color, #e0e0e0);
    background: var(--app-header-background-color, #f5f5f5);
  }

  .header h2 {
    margin: 0;
    font-size: 18px;
    font-weight: 500;
    color: var(--primary-text-color, #212121);
  }

  .header-actions {
    display: flex;
    gap: 8px;
  }

  /* Mode Selector */
  .mode-selector {
    display: flex;
    gap: 8px;
    padding: 12px 20px;
    border-bottom: 1px solid var(--divider-color, #e0e0e0);
    background: var(--card-background-color, #ffffff);
  }

  /* Web Toggle */
  .web-toggle-container {
    display: flex;
    justify-content: space-between;
    align-items: center;
    padding: 12px 20px;
    border-bottom: 1px solid var(--divider-color, #e0e0e0);
    background: var(--card-background-color, #ffffff);
  }

  .web-toggle {
    display: flex;
    align-items: center;
    gap: 10px;
    cursor: pointer;
    position: relative;
  }

  .web-toggle input[type="checkbox"] {
    display: none;
  }

  .toggle-slider {
    width: 44px;
    height: 24px;
    background: var(--divider-color, #e0e0e0);
    border-radius: 12px;
    position: relative;
    transition: background 0.3s ease;
  }

  .toggle-slider::before {
    content: '';
    position: absolute;
    width: 20px;
    height: 20px;
    border-radius: 50%;
    background: white;
    top: 2px;
    left: 2px;
    transition: transform 0.3s ease;
    box-shadow: 0 2px 4px rgba(0,0,0,0.2);
  }

  .web-toggle input[type="checkbox"]:checked + .toggle-slider {
    background: var(--primary-color, #03a9f4);
  }

  .web-toggle input[type="checkbox"]:checked + .toggle-slider::before {
    transform: translateX(20px);
  }

  .toggle-label {
    font-size: 13px;
    color: var(--primary-text-color, #212121);
    font-weight: 500;
    position: relative;
  }

  .tooltip {
    visibility: hidden;
    position: absolute;
    bottom: 100%;
    left: 50%;
    transform: translateX(-50%);
    background: var(--primary-text-color, #212121);
    color: white;
    padding: 6px 10px;
    border-radius: 6px;
    font-size: 11px;
    white-space: nowrap;
    z-index: 1000;
    opacity: 0;
    transition: opacity 0.2s ease;
  }

  .toggle-label:hover .tooltip {
    visibility: visible;
    opacity: 1;
  }

  /* Query Type Badge */
  .query-type-badge {
    padding: 6px 12px;
    border-radius: 16px;
    font-size: 12px;
    font-weight: 600;
    display: flex;
    align-items: center;
    gap: 6px;
    animation: fadeIn 0.3s ease;
  }

  .query-type-badge.local {
    background: rgba(76, 175, 80, 0.1);
    color: var(--success-color, #4caf50);
    border: 1px solid var(--success-color, #4caf50);
  }

  .query-type-badge.web {
    background: rgba(3, 169, 244, 0.1);
    color: var(--primary-color, #03a9f4);
    border: 1px solid var(--primary-color, #03a9f4);
  }

  .query-type-badge.hybrid {
    background: rgba(156, 39, 176, 0.1);
    color: #9c27b0;
    border: 1px solid #9c27b0;
  }

  /* Sources Section */
  .sources-section {
    margin-top: 12px;
    padding: 12px;
    background: rgba(3, 169, 244, 0.05);
    border-radius: 8px;
    border-left: 3px solid var(--primary-color, #03a9f4);
  }

  .sources-list {
    display: flex;
    flex-wrap: wrap;
    gap: 6px;
    margin-top: 8px;
  }

  .source-badge {
    padding: 4px 10px;
    background: var(--card-background-color, #ffffff);
    border: 1px solid var(--divider-color, #e0e0e0);
    border-radius: 12px;
    font-size: 11px;
    color: var(--secondary-text-color, #757575);
    font-weight: 500;
  }

  .mode-btn {
    flex: 1;
    padding: 8px 16px;
    border: 2px solid var(--primary-color, #03a9f4);
    background: transparent;
    color: var(--primary-color, #03a9f4);
    border-radius: 20px;
    cursor: pointer;
    font-size: 13px;
    font-weight: 500;
    transition: all 0.2s ease;
  }

  .mode-btn:hover {
    background: rgba(3, 169, 244, 0.1);
  }

  .mode-btn.active {
    background: var(--primary-color, #03a9f4);
    color: white;
  }

  /* Chat Area */
  .chat-area {
    flex: 1;
    overflow-y: auto;
    padding: 20px;
    display: flex;
    flex-direction: column;
    gap: 16px;
  }

  .chat-message {
    display: flex;
    gap: 12px;
    animation: fadeIn 0.3s ease;
  }

  @keyframes fadeIn {
    from { opacity: 0; transform: translateY(10px); }
    to { opacity: 1; transform: translateY(0); }
  }

  .chat-message.user {
    justify-content: flex-end;
  }

  .chat-message.assistant {
    justify-content: flex-start;
  }

  .message-bubble {
    max-width: 80%;
    padding: 12px 16px;
    border-radius: 16px;
    font-size: 14px;
    line-height: 1.5;
  }

  .user .message-bubble {
    background: var(--primary-color, #03a9f4);
    color: white;
    border-bottom-right-radius: 4px;
  }

  .assistant .message-bubble {
    background: var(--card-background-color, #f5f5f5);
    color: var(--primary-text-color, #212121);
    border-bottom-left-radius: 4px;
    border: 1px solid var(--divider-color, #e0e0e0);
  }

  /* Results */
  .results-container {
    margin-top: 12px;
  }

  .results-header {
    display: flex;
    justify-content: space-between;
    align-items: center;
    margin-bottom: 8px;
    font-size: 12px;
    color: var(--secondary-text-color, #757575);
  }

  .results-list {
    display: flex;
    flex-direction: column;
    gap: 8px;
  }

  .result-item {
    padding: 12px;
    background: var(--card-background-color, #ffffff);
    border: 1px solid var(--divider-color, #e0e0e0);
    border-radius: 8px;
    cursor: pointer;
    transition: all 0.2s ease;
  }

  .result-item:hover {
    border-color: var(--primary-color, #03a9f4);
    box-shadow: 0 2px 8px rgba(3, 169, 244, 0.15);
  }

  .result-item.selected {
    border-color: var(--primary-color, #03a9f4);
    background: rgba(3, 169, 244, 0.05);
  }

  .result-header {
    display: flex;
    justify-content: space-between;
    align-items: center;
    margin-bottom: 6px;
  }

  .result-id {
    font-weight: 500;
    font-size: 13px;
    color: var(--primary-text-color, #212121);
  }

  .result-score {
    display: flex;
    gap: 8px;
    font-size: 11px;
  }

  .score-badge {
    padding: 2px 6px;
    border-radius: 4px;
    background: var(--primary-color, #03a9f4);
    color: white;
    font-weight: 500;
  }

  .score-badge.lexical {
    background: var(--accent-color, #ff9800);
  }

  .score-badge.semantic {
    background: var(--success-color, #4caf50);
  }

  .result-text {
    font-size: 13px;
    color: var(--secondary-text-color, #757575);
    line-height: 1.4;
    display: -webkit-box;
    -webkit-line-clamp: 3;
    -webkit-box-orient: vertical;
    overflow: hidden;
  }

  .result-metadata {
    margin-top: 6px;
    font-size: 11px;
    color: var(--secondary-text-color, #9e9e9e);
  }

  /* Loading State */
  .loading-container {
    display: flex;
    flex-direction: column;
    align-items: center;
    justify-content: center;
    padding: 40px;
    gap: 16px;
  }

  .spinner {
    width: 40px;
    height: 40px;
    border: 4px solid var(--divider-color, #e0e0e0);
    border-top-color: var(--primary-color, #03a9f4);
    border-radius: 50%;
    animation: spin 1s linear infinite;
  }

  @keyframes spin {
    to { transform: rotate(360deg); }
  }

  .loading-text {
    font-size: 14px;
    color: var(--secondary-text-color, #757575);
  }

  /* Error State */
  .error-container {
    padding: 16px;
    background: rgba(244, 67, 54, 0.1);
    border: 1px solid var(--error-color, #f44336);
    border-radius: 8px;
    color: var(--error-color, #f44336);
    font-size: 14px;
  }

  /* Input Area */
  .input-area {
    display: flex;
    gap: 12px;
    padding: 16px 20px;
    border-top: 1px solid var(--divider-color, #e0e0e0);
    background: var(--card-background-color, #ffffff);
  }

  .search-input {
    flex: 1;
    padding: 12px 16px;
    border: 2px solid var(--divider-color, #e0e0e0);
    border-radius: 24px;
    font-size: 14px;
    font-family: inherit;
    outline: none;
    transition: border-color 0.2s ease;
  }

  .search-input:focus {
    border-color: var(--primary-color, #03a9f4);
  }

  .search-btn {
    padding: 12px 24px;
    background: var(--primary-color, #03a9f4);
    color: white;
    border: none;
    border-radius: 24px;
    font-size: 14px;
    font-weight: 500;
    cursor: pointer;
    transition: all 0.2s ease;
    display: flex;
    align-items: center;
    gap: 8px;
  }

  .search-btn:hover:not(:disabled) {
    background: var(--primary-color-dark, #0288d1);
    transform: translateY(-1px);
    box-shadow: 0 4px 12px rgba(3, 169, 244, 0.3);
  }

  .search-btn:disabled {
    opacity: 0.6;
    cursor: not-allowed;
  }

  .search-btn svg {
    width: 18px;
    height: 18px;
  }

  /* History Panel */
  .history-panel {
    position: absolute;
    top: 60px;
    right: 20px;
    width: 300px;
    max-height: 400px;
    background: var(--card-background-color, #ffffff);
    border: 1px solid var(--divider-color, #e0e0e0);
    border-radius: 8px;
    box-shadow: 0 4px 20px rgba(0,0,0,0.15);
    z-index: 100;
    overflow: hidden;
  }

  .history-header {
    display: flex;
    justify-content: space-between;
    align-items: center;
    padding: 12px 16px;
    border-bottom: 1px solid var(--divider-color, #e0e0e0);
    font-weight: 500;
    font-size: 14px;
  }

  .history-close {
    background: none;
    border: none;
    cursor: pointer;
    padding: 4px;
    color: var(--secondary-text-color, #757575);
  }

  .history-list {
    max-height: 300px;
    overflow-y: auto;
  }

  .history-item {
    padding: 12px 16px;
    border-bottom: 1px solid var(--divider-color, #e0e0e0);
    cursor: pointer;
    transition: background 0.2s ease;
  }

  .history-item:hover {
    background: rgba(3, 169, 244, 0.05);
  }

  .history-query {
    font-size: 13px;
    font-weight: 500;
    margin-bottom: 4px;
  }

  .history-meta {
    font-size: 11px;
    color: var(--secondary-text-color, #9e9e9e);
    display: flex;
    justify-content: space-between;
  }

  /* Empty State */
  .empty-state {
    display: flex;
    flex-direction: column;
    align-items: center;
    justify-content: center;
    padding: 60px 20px;
    text-align: center;
    color: var(--secondary-text-color, #757575);
  }

  .empty-state svg {
    width: 80px;
    height: 80px;
    margin-bottom: 16px;
    opacity: 0.5;
  }

  .empty-state h3 {
    margin: 0 0 8px 0;
    font-size: 16px;
    font-weight: 500;
  }

  .empty-state p {
    margin: 0;
    font-size: 13px;
    line-height: 1.5;
  }

  /* Selected Result Detail */
  .result-detail {
    margin-top: 16px;
    padding: 16px;
    background: var(--card-background-color, #f9f9f9);
    border: 1px solid var(--divider-color, #e0e0e0);
    border-radius: 8px;
  }

  .result-detail h4 {
    margin: 0 0 12px 0;
    font-size: 14px;
    font-weight: 500;
  }

  .result-detail-text {
    font-size: 13px;
    line-height: 1.6;
    color: var(--primary-text-color, #212121);
    white-space: pre-wrap;
  }
`;

export default ragChatStyles;
