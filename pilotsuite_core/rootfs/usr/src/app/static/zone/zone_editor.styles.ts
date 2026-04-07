/**
 * Zone Editor Styles
 * 
 * Home Assistant Design System compatible styles
 * for the Zone Editor component
 * 
 * @author Clawdya
 * @version 1.0.0
 */

import { css } from 'lit';

export const zoneEditorStyles = css`
  :host {
    display: block;
    font-family: var(--ha-font-family, 'Roboto', sans-serif);
    color: var(--primary-text-color, #212121);
    background: var(--card-background-color, #ffffff);
    border-radius: var(--ha-card-border-radius, 8px);
    box-shadow: var(--ha-card-box-shadow, 0 2px 4px rgba(0,0,0,0.1));
    overflow: hidden;
  }

  .zone-editor-container {
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

  /* Buttons */
  .btn {
    padding: 8px 16px;
    border: none;
    border-radius: 6px;
    font-size: 13px;
    font-weight: 500;
    cursor: pointer;
    transition: all 0.2s ease;
    display: inline-flex;
    align-items: center;
    gap: 6px;
  }

  .btn:disabled {
    opacity: 0.6;
    cursor: not-allowed;
  }

  .btn-primary {
    background: var(--primary-color, #03a9f4);
    color: white;
  }

  .btn-primary:hover:not(:disabled) {
    background: var(--primary-color-dark, #0288d1);
    transform: translateY(-1px);
    box-shadow: 0 4px 12px rgba(3, 169, 244, 0.3);
  }

  .btn-secondary {
    background: var(--card-background-color, #f5f5f5);
    color: var(--primary-text-color, #212121);
    border: 1px solid var(--divider-color, #e0e0e0);
  }

  .btn-secondary:hover:not(:disabled) {
    background: var(--divider-color, #e0e0e0);
  }

  .btn-danger {
    background: var(--error-color, #f44336);
    color: white;
  }

  .btn-danger:hover:not(:disabled) {
    background: #d32f2f;
  }

  .btn-icon {
    padding: 4px 8px;
    background: transparent;
    border: none;
    cursor: pointer;
    color: var(--secondary-text-color, #757575);
    font-size: 16px;
  }

  .btn-icon:hover {
    color: var(--primary-text-color, #212121);
  }

  /* Messages */
  .message {
    padding: 12px 20px;
    font-size: 13px;
    animation: slideIn 0.3s ease;
  }

  @keyframes slideIn {
    from { opacity: 0; transform: translateY(-10px); }
    to { opacity: 1; transform: translateY(0); }
  }

  .message.success {
    background: rgba(76, 175, 80, 0.1);
    border-left: 4px solid var(--success-color, #4caf50);
    color: var(--success-color, #4caf50);
  }

  .message.error {
    background: rgba(244, 67, 54, 0.1);
    border-left: 4px solid var(--error-color, #f44336);
    color: var(--error-color, #f44336);
  }

  /* Main Content */
  .main-content {
    flex: 1;
    display: flex;
    overflow: hidden;
  }

  /* Zone List Panel */
  .zone-list-panel {
    width: 280px;
    border-right: 1px solid var(--divider-color, #e0e0e0);
    overflow-y: auto;
    background: var(--card-background-color, #ffffff);
  }

  .zone-list-panel h3 {
    margin: 0;
    padding: 12px 16px;
    font-size: 13px;
    font-weight: 500;
    color: var(--secondary-text-color, #757575);
    text-transform: uppercase;
    letter-spacing: 0.5px;
    border-bottom: 1px solid var(--divider-color, #e0e0e0);
  }

  .zone-list {
    display: flex;
    flex-direction: column;
  }

  .zone-list-item {
    display: flex;
    align-items: center;
    gap: 12px;
    padding: 12px 16px;
    cursor: pointer;
    transition: all 0.2s ease;
    border-bottom: 1px solid var(--divider-color, #e0e0e0);
  }

  .zone-list-item:hover {
    background: rgba(3, 169, 244, 0.05);
  }

  .zone-list-item.selected {
    background: rgba(3, 169, 244, 0.1);
    border-left: 3px solid var(--primary-color, #03a9f4);
  }

  .zone-icon {
    width: 40px;
    height: 40px;
    border-radius: 8px;
    background: var(--primary-color, #03a9f4);
    color: white;
    display: flex;
    align-items: center;
    justify-content: center;
    font-size: 18px;
  }

  .zone-info {
    flex: 1;
    min-width: 0;
  }

  .zone-name {
    font-weight: 500;
    font-size: 14px;
    color: var(--primary-text-color, #212121);
    white-space: nowrap;
    overflow: hidden;
    text-overflow: ellipsis;
  }

  .zone-meta {
    font-size: 11px;
    color: var(--secondary-text-color, #757575);
    margin-top: 2px;
  }

  /* Zone Detail Panel */
  .zone-detail-panel {
    flex: 1;
    overflow-y: auto;
    padding: 20px;
    background: var(--card-background-color, #f9f9f9);
  }

  .zone-detail {
    background: var(--card-background-color, #ffffff);
    border-radius: 8px;
    padding: 20px;
    box-shadow: 0 2px 4px rgba(0,0,0,0.05);
  }

  .detail-header {
    display: flex;
    justify-content: space-between;
    align-items: center;
    margin-bottom: 20px;
    padding-bottom: 16px;
    border-bottom: 1px solid var(--divider-color, #e0e0e0);
  }

  .detail-header h3 {
    margin: 0;
    font-size: 20px;
    font-weight: 500;
  }

  .detail-actions {
    display: flex;
    gap: 8px;
  }

  .detail-info {
    margin-bottom: 24px;
  }

  .info-row {
    display: flex;
    justify-content: space-between;
    padding: 8px 0;
    border-bottom: 1px solid var(--divider-color, #e0e0e0);
  }

  .info-row:last-child {
    border-bottom: none;
  }

  .info-row .label {
    font-weight: 500;
    color: var(--secondary-text-color, #757575);
    font-size: 13px;
  }

  .info-row .value {
    color: var(--primary-text-color, #212121);
    font-size: 13px;
  }

  .entities-section h4 {
    margin: 0 0 12px 0;
    font-size: 14px;
    font-weight: 500;
  }

  .no-entities {
    color: var(--secondary-text-color, #9e9e9e);
    font-size: 13px;
    font-style: italic;
  }

  /* Entity List */
  .entity-list {
    display: flex;
    flex-direction: column;
    gap: 8px;
  }

  .entity-item {
    display: flex;
    align-items: center;
    gap: 12px;
    padding: 10px 12px;
    background: var(--card-background-color, #f5f5f5);
    border-radius: 6px;
    font-size: 13px;
  }

  .entity-item.removable {
    justify-content: space-between;
  }

  .entity-domain {
    padding: 2px 6px;
    background: var(--primary-color, #03a9f4);
    color: white;
    border-radius: 4px;
    font-size: 10px;
    font-weight: 500;
    text-transform: uppercase;
  }

  .entity-name {
    flex: 1;
    font-weight: 500;
    color: var(--primary-text-color, #212121);
  }

  .entity-id {
    color: var(--secondary-text-color, #757575);
    font-size: 11px;
    font-family: monospace;
  }

  .btn-remove {
    width: 24px;
    height: 24px;
    border-radius: 50%;
    border: none;
    background: var(--error-color, #f44336);
    color: white;
    cursor: pointer;
    display: flex;
    align-items: center;
    justify-content: center;
    font-size: 12px;
    transition: all 0.2s ease;
  }

  .btn-remove:hover {
    background: #d32f2f;
    transform: scale(1.1);
  }

  /* Draggable Entity */
  .draggable-entity {
    display: flex;
    align-items: center;
    gap: 8px;
    padding: 8px 12px;
    background: var(--card-background-color, #ffffff);
    border: 1px solid var(--divider-color, #e0e0e0);
    border-radius: 6px;
    cursor: grab;
    transition: all 0.2s ease;
  }

  .draggable-entity:hover {
    border-color: var(--primary-color, #03a9f4);
    box-shadow: 0 2px 8px rgba(3, 169, 244, 0.15);
  }

  .draggable-entity:active {
    cursor: grabbing;
  }

  /* Entity Drop Zone */
  .entity-drop-zone {
    min-height: 100px;
    padding: 12px;
    background: var(--card-background-color, #f5f5f5);
    border: 2px dashed var(--divider-color, #e0e0e0);
    border-radius: 6px;
    transition: all 0.2s ease;
  }

  .entity-drop-zone.dragover {
    border-color: var(--primary-color, #03a9f4);
    background: rgba(3, 169, 244, 0.05);
  }

  .drop-placeholder {
    display: flex;
    align-items: center;
    justify-content: center;
    height: 80px;
    color: var(--secondary-text-color, #9e9e9e);
    font-size: 13px;
    font-style: italic;
  }

  /* Available Entities Panel */
  .available-entities-panel {
    padding: 16px 20px;
    border-top: 1px solid var(--divider-color, #e0e0e0);
    background: var(--card-background-color, #ffffff);
  }

  .available-entities-panel h3 {
    margin: 0 0 4px 0;
    font-size: 13px;
    font-weight: 500;
  }

  .available-entities-panel .hint {
    margin: 0 0 12px 0;
    font-size: 11px;
    color: var(--secondary-text-color, #9e9e9e);
  }

  .available-entities-panel .entity-list {
    display: flex;
    flex-wrap: wrap;
    gap: 8px;
  }

  /* Form */
  .form-container {
    background: var(--card-background-color, #ffffff);
    border-radius: 8px;
    padding: 20px;
    box-shadow: 0 2px 4px rgba(0,0,0,0.05);
  }

  .form-header {
    display: flex;
    justify-content: space-between;
    align-items: center;
    margin-bottom: 20px;
  }

  .form-header h3 {
    margin: 0;
    font-size: 18px;
    font-weight: 500;
  }

  .form-group {
    margin-bottom: 16px;
  }

  .form-group label {
    display: block;
    margin-bottom: 6px;
    font-size: 13px;
    font-weight: 500;
    color: var(--primary-text-color, #212121);
  }

  .form-group input {
    width: 100%;
    padding: 10px 12px;
    border: 2px solid var(--divider-color, #e0e0e0);
    border-radius: 6px;
    font-size: 14px;
    font-family: inherit;
    outline: none;
    transition: border-color 0.2s ease;
    box-sizing: border-box;
  }

  .form-group input:focus {
    border-color: var(--primary-color, #03a9f4);
  }

  .form-group input:disabled {
    background: var(--divider-color, #e0e0e0);
    cursor: not-allowed;
  }

  .form-group input.disabled-input {
    background: var(--divider-color, #e0e0e0);
    cursor: not-allowed;
  }

  .form-row {
    display: flex;
    gap: 16px;
  }

  .form-row .form-group {
    flex: 1;
  }

  .error-text {
    color: var(--error-color, #f44336);
    font-size: 11px;
    margin-top: 4px;
  }

  .form-actions {
    display: flex;
    justify-content: flex-end;
    gap: 12px;
    margin-top: 20px;
    padding-top: 16px;
    border-top: 1px solid var(--divider-color, #e0e0e0);
  }

  /* Empty State */
  .empty-state {
    display: flex;
    flex-direction: column;
    align-items: center;
    justify-content: center;
    height: 100%;
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

  /* Loading Skeleton */
  .skeleton-list {
    display: flex;
    flex-direction: column;
    gap: 12px;
    padding: 16px;
  }

  .skeleton-item {
    display: flex;
    align-items: center;
    gap: 12px;
  }

  .skeleton-line {
    height: 12px;
    background: linear-gradient(90deg, #f0f0f0 25%, #e0e0e0 50%, #f0f0f0 75%);
    background-size: 200% 100%;
    animation: shimmer 1.5s infinite;
    border-radius: 4px;
  }

  @keyframes shimmer {
    0% { background-position: 200% 0; }
    100% { background-position: -200% 0; }
  }

  .skeleton-line.short {
    width: 40px;
    height: 40px;
    border-radius: 8px;
  }

  .skeleton-line:nth-child(2) {
    flex: 1;
    width: 100%;
  }

  /* Spinner */
  .spinner {
    width: 16px;
    height: 16px;
    border: 2px solid rgba(255, 255, 255, 0.3);
    border-top-color: white;
    border-radius: 50%;
    animation: spin 0.8s linear infinite;
  }

  @keyframes spin {
    to { transform: rotate(360deg); }
  }

  /* Responsive */
  @media (max-width: 768px) {
    .main-content {
      flex-direction: column;
    }

    .zone-list-panel {
      width: 100%;
      border-right: none;
      border-bottom: 1px solid var(--divider-color, #e0e0e0);
      max-height: 200px;
    }

    .form-row {
      flex-direction: column;
      gap: 0;
    }
  }
`;

export default zoneEditorStyles;
