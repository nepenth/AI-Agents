/* Lightweight, trusted markdown renderer + sanitizer for KB and Synthesis modals.
 * - Uses markdown-it (loaded by markdownLoader.js) when available
 * - Falls back gracefully if libs fail
 * - Minimal code highlighting similar to chat renderer
 */
(function () {
  'use strict';

  function escapeHtml(text) {
    const div = document.createElement('div');
    div.textContent = text == null ? '' : String(text);
    return div.innerHTML;
  }

  function simpleHighlight(str, lang) {
    if (!lang) return escapeHtml(str);
    const keywords = {
      javascript: ['function', 'const', 'let', 'var', 'if', 'else', 'for', 'while', 'return', 'class', 'async', 'await'],
      python: ['def', 'class', 'if', 'else', 'elif', 'for', 'while', 'return', 'import', 'from', 'try', 'except'],
      bash: ['echo', 'cd', 'ls', 'mkdir', 'rm', 'cp', 'mv', 'grep', 'find', 'chmod', 'sudo'],
      sql: ['SELECT', 'FROM', 'WHERE', 'INSERT', 'UPDATE', 'DELETE', 'CREATE', 'ALTER', 'DROP'],
      css: ['color', 'background', 'margin', 'padding', 'border', 'display', 'position', 'flex'],
      html: ['div', 'span', 'p', 'h1', 'h2', 'h3', 'a', 'img', 'ul', 'li', 'table']
    };
    let highlighted = escapeHtml(str);
    const set = keywords[String(lang).toLowerCase()];
    if (set) {
      set.forEach((kw) => {
        const re = new RegExp('\\b' + kw + '\\b', 'g');
        highlighted = highlighted.replace(re, '<span class="code-keyword">' + kw + '</span>');
      });
    }
    highlighted = highlighted
      .replace(/(["'])((?:\\.|(?!\1)[^\\])*?)\1/g, '<span class="code-string">$1$2$1</span>');
    if (lang === 'javascript' || lang === 'css') {
      highlighted = highlighted.replace(/(\/\/.*$)/gm, '<span class="code-comment">$1</span>')
                               .replace(/(\/\*[\s\S]*?\*\/)/g, '<span class="code-comment">$1</span>');
    } else if (lang === 'python' || lang === 'bash') {
      highlighted = highlighted.replace(/(#.*$)/gm, '<span class="code-comment">$1</span>');
    }
    return highlighted;
  }

  function getMarkdownIt() {
    if (typeof markdownit === 'undefined') return null;
    try {
      return markdownit({ html: false, breaks: true, linkify: true, typographer: true, highlight: simpleHighlight });
    } catch (e) {
      console.warn('markdown-it init failed:', e);
      return null;
    }
  }

  function sanitize(html) {
    try {
      if (window.DOMPurify && typeof window.DOMPurify.sanitize === 'function') {
        return window.DOMPurify.sanitize(html, { ALLOWED_TAGS: false, ALLOWED_ATTR: false });
      }
    } catch (e) {
      console.warn('DOMPurify sanitize failed:', e);
    }
    return html;
  }

  function renderMarkdown(mdText) {
    const text = mdText == null ? '' : String(mdText);
    const md = getMarkdownIt();
    if (md) {
      try { return md.render(text); } catch (_) {}
    }
    // Fallback minimal rendering
    let html = text
      .replace(/^### (.*$)/gm, '<h3>$1</h3>')
      .replace(/^## (.*$)/gm, '<h2>$1</h2>')
      .replace(/^# (.*$)/gm, '<h1>$1</h1>')
      .replace(/\*\*([^*]+)\*\*/g, '<strong>$1</strong>')
      .replace(/\*([^*]+)\*/g, '<em>$1</em>')
      .replace(/`([^`]+)`/g, '<code class="inline-code">$1</code>')
      .replace(/\[([^\]]+)\]\(([^)]+)\)/g, '<a href="$2" target="_blank" rel="noopener noreferrer">$1</a>')
      .replace(/\n\n/g, '</p><p>');
    html = '<p>' + html + '</p>';
    return html;
  }

  function renderAndSanitize(mdText) {
    return sanitize(renderMarkdown(mdText));
  }

  window.ContentRenderer = {
    renderMarkdown,
    sanitizeHTML: sanitize,
    renderAndSanitize
  };
})();


