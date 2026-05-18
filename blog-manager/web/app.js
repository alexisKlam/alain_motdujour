const state = {
    articles: [],
    activePath: "",
    rawMode: true,
    editorMode: "raw",
    categoryOptions: [],
    tagOptions: [],
    editorSelection: null,
    draggedMedia: null,
};

const DEFAULT_ARTICLE_TEMPLATE = `<div class="mdjTexte">« Citation du jour »</div>
<div class="mdjAuteur">Auteur de la citation</div>

<p><span style="color: #777777; font-family: arial;">Premier paragraphe de l'article.</span></p>

<p style="margin-left: 28pt;"><span style="color: #c00000; font-family: arial;">« Citation ou extrait en retrait. »</span></p>

<p><span style="color: #777777; font-family: arial;">Suite de l'article.</span></p>
`;

const $ = (id) => document.getElementById(id);

const STYLE_SNIPPETS = {
    quoteHeader: `<div class="mdjTexte">« Citation du jour »</div>
<div class="mdjAuteur">Auteur de la citation</div>`,
    grayText: `<p><span style="color: #777777; font-family: arial;">Texte du paragraphe.</span></p>`,
    redQuote: `<div class="mdjTexte">« Citation ou extrait en retrait. »</div>`,
    imageText: `<p><span style="color: #777777; font-family: arial;"><img loading="lazy" decoding="async" class="alignleft" src="/wp-content/uploads/AAAA/MM/image.jpg" alt="" width="300" />Texte à côté de l'image.</span></p>`,
};

function log(message) {
    const node = $("logOutput");
    const text = typeof message === "string" ? message : JSON.stringify(message, null, 2);
    node.textContent = `${new Date().toLocaleTimeString("fr-FR")} ${text}\n\n${node.textContent}`.slice(0, 20000);
}

async function api(path, options = {}) {
    const response = await fetch(path, options);
    const payload = await response.json();
    if (!response.ok) {
        throw new Error(payload.error || "Erreur inconnue");
    }
    return payload;
}

async function refreshArticles() {
    const payload = await api("/api/articles");
    state.articles = payload.articles;
    refreshAutocompleteOptions();
    renderArticleList();
    $("statusLine").textContent = payload.frontpage?.mode === "manual"
        ? `Premiere page manuelle: ${payload.frontpage.permalink}`
        : "Premiere page: dernier article par date";
    if (!state.activePath && state.articles.length) {
        await loadArticle(state.articles[0].path);
    }
}

function refreshAutocompleteOptions() {
    state.categoryOptions = collectOptions("categories");
    state.tagOptions = collectOptions("tags");
}

function collectOptions(field) {
    const values = new Map();
    state.articles.forEach((article) => {
        (article[field] || []).forEach((value) => {
            const text = String(value || "").trim();
            if (text) {
                values.set(text.toLowerCase(), text);
            }
        });
    });
    return [...values.values()].sort((a, b) => a.localeCompare(b, "fr", {sensitivity: "base"}));
}

function renderArticleList() {
    const query = $("searchInput").value.trim().toLowerCase();
    const items = state.articles.filter((article) => {
        const haystack = `${article.title} ${article.date} ${(article.tags || []).join(" ")} ${article.excerpt}`.toLowerCase();
        return !query || haystack.includes(query);
    });
    $("articleList").innerHTML = items.map((article) => `
        <button class="article-item compact ${article.path === state.activePath ? "active" : ""}" data-path="${escapeHtml(article.path)}" title="${escapeHtml(article.title)}">
            <strong>${escapeHtml(formatArticleDate(article.date))}</strong>
        </button>
    `).join("");
    document.querySelectorAll(".article-item").forEach((button) => {
        button.addEventListener("click", () => loadArticle(button.dataset.path));
    });
}

async function loadArticle(path) {
    syncRawFromActiveEditor();
    const article = await api(`/api/article?path=${encodeURIComponent(path)}`);
    state.activePath = article.path;
    $("titleInput").value = article.meta.title || "";
    $("dateInput").value = normalizeDate(article.meta.date || "");
    $("aliasesInput").value = listToText(article.meta.aliases);
    $("categoriesInput").value = listToText(article.meta.categories);
    $("tagsInput").value = listToText(article.meta.tags);
    $("authorInput").value = article.meta.author || "alain";
    $("markdownEditor").value = article.content || "";
    $("visualEditor").innerHTML = markdownToHtml(article.content || "");
    $("screenTitle").textContent = article.meta.title || "Editeur";
    setEditorMode("raw", {sync: false});
    renderArticleList();
}

function newArticle() {
    const today = new Date().toISOString().slice(0, 10);
    state.activePath = "";
    $("titleInput").value = `Article du ${today}`;
    $("dateInput").value = today;
    $("aliasesInput").value = "";
    $("categoriesInput").value = "Mot du jour";
    $("tagsInput").value = "";
    $("authorInput").value = "alain";
    $("markdownEditor").value = DEFAULT_ARTICLE_TEMPLATE;
    $("visualEditor").innerHTML = markdownToHtml(DEFAULT_ARTICLE_TEMPLATE);
    $("previewBody").innerHTML = "";
    state.editorSelection = null;
    $("screenTitle").textContent = "Nouvel article";
    setEditorMode("raw", {sync: false});
    renderArticleList();
}

async function saveArticle() {
    syncRawFromActiveEditor();
    const dateValue = $("dateInput").value || new Date().toISOString().slice(0, 10);
    const payload = {
        path: state.activePath,
        meta: {
            title: $("titleInput").value.trim() || "Nouvel article",
            author: $("authorInput").value.trim() || "alain",
            type: "post",
            date: `${dateValue}T00:00:00+00:00`,
            aliases: textToList($("aliasesInput").value),
            categories: textToList($("categoriesInput").value),
            tags: textToList($("tagsInput").value),
        },
        content: $("markdownEditor").value,
    };
    const result = await api("/api/save_article", {
        method: "POST",
        headers: {"Content-Type": "application/json"},
        body: JSON.stringify(payload),
    });
    state.activePath = result.article.path;
    log(`Article enregistré: ${state.activePath}`);
    await refreshArticles();
    await loadArticle(state.activePath);
}

async function importDocx(file) {
    const body = new FormData();
    body.set("file", file);
    body.set("title", $("titleInput").value || file.name.replace(/\.docx$/i, ""));
    body.set("date", $("dateInput").value || new Date().toISOString().slice(0, 10));
    const result = await api("/api/import_docx", {method: "POST", body});
    log(`Word importé: ${result.article.path}`);
    await refreshArticles();
    await loadArticle(result.article.path);
}

async function importMedia(file) {
    const body = new FormData();
    body.set("file", file);
    body.set("date", $("dateInput").value || new Date().toISOString().slice(0, 10));
    const result = await api("/api/import_media", {method: "POST", body});
    insertMedia(result.url, file.name);
    log(`Media importé: ${result.url}`);
}

async function setHomepage(useDefault) {
    const payload = useDefault ? {default: true} : {path: state.activePath};
    const result = await api("/api/set_homepage", {
        method: "POST",
        headers: {"Content-Type": "application/json"},
        body: JSON.stringify(payload),
    });
    log(result.frontpage.mode === "manual" ? `Premiere page: ${result.frontpage.permalink}` : "Premiere page: dernier article");
    await refreshArticles();
}

async function buildSite() {
    const result = await api("/api/build", {method: "POST", headers: {"Content-Type": "application/json"}, body: "{}"});
    log(formatCommandResult(result));
}

function previewArticle() {
    setEditorMode("preview");
}

async function refreshGit() {
    const payload = await api("/api/git/status");
    $("gitPanel").hidden = false;
    $("gitFiles").innerHTML = payload.files.map((file) => `
        <label>
            <input type="checkbox" value="${escapeHtml(file.path)}" ${defaultGitChecked(file.path) ? "checked" : ""}>
            <code>${escapeHtml(file.status)}</code>
            <span>${escapeHtml(file.path)}</span>
        </label>
    `).join("") || "<p>Aucun changement.</p>";
}

async function commitPush() {
    const files = [...$("gitFiles").querySelectorAll("input:checked")].map((input) => input.value);
    const result = await api("/api/git/commit_push", {
        method: "POST",
        headers: {"Content-Type": "application/json"},
        body: JSON.stringify({
            files,
            message: $("commitMessageInput").value,
            push: $("pushCheckbox").checked,
        }),
    });
    log(formatCommandResult(result.commit));
    if (result.push) {
        log(formatCommandResult(result.push));
    }
    await refreshGit();
}

function applyToolbar(button) {
    const command = button.dataset.command;
    const value = button.dataset.value || null;

    if (state.editorMode === "raw") {
        applyRawToolbar(command, value);
        return;
    }

    restoreEditorSelection();
    const normalizedValue = command === "formatBlock" && value ? `<${value}>` : value;
    document.execCommand(command, false, normalizedValue);
    syncRawFromActiveEditor();
    rememberEditorSelection();
}

function createLink() {
    const url = window.prompt("URL du lien");
    if (!url) {
        return;
    }
    restoreEditorSelection();
    document.execCommand("createLink", false, url);
    syncRawFromActiveEditor();
    rememberEditorSelection();
}

function cleanFormatting() {
    if (state.editorMode === "raw") {
        cleanRawSelection();
        return;
    }
    restoreEditorSelection();
    const selection = window.getSelection();
    if (!selection || !selection.rangeCount || selection.isCollapsed) {
        return;
    }
    document.execCommand("removeFormat", false, null);
    syncRawFromActiveEditor();
    rememberEditorSelection();
}

function cleanRawSelection() {
    const textarea = $("markdownEditor");
    const start = textarea.selectionStart || 0;
    const end = textarea.selectionEnd || 0;
    if (start === end) {
        textarea.focus();
        return;
    }
    const selected = textarea.value.slice(start, end);
    const cleaned = cleanTextFormatting(selected);
    textarea.value = textarea.value.slice(0, start) + cleaned + textarea.value.slice(end);
    textarea.selectionStart = start;
    textarea.selectionEnd = start + cleaned.length;
    textarea.focus();
}

function setEditorMode(mode, options = {}) {
    const previousMode = state.editorMode;
    const scrollRatio = captureEditorScrollRatio(previousMode);
    const shouldSync = options.sync !== false;
    if (shouldSync && state.editorMode !== mode) {
        syncRawFromActiveEditor();
    }
    if (mode === "preview") {
        renderPreview({
            title: $("titleInput").value.trim() || "Article",
            date: $("dateInput").value,
            categories: textToList($("categoriesInput").value),
            content: $("markdownEditor").value,
        });
    }

    const shell = document.querySelector(".editor-shell");
    state.editorMode = mode;
    state.rawMode = mode === "raw";
    state.editorSelection = null;
    shell.classList.toggle("raw", mode === "raw");
    shell.classList.toggle("preview", mode === "preview");
    document.querySelectorAll("[data-mode-button]").forEach((button) => {
        button.classList.toggle("active", button.dataset.modeButton === mode);
    });
    applyEditorScrollRatio(mode, scrollRatio);
}

function syncRawFromActiveEditor() {
    if (state.editorMode === "visual") {
        syncRawFromVisual();
    }
    if (state.editorMode === "preview") {
        syncRawFromPreview();
    }
}

function syncRawFromVisual() {
    if (state.editorMode === "visual") {
        $("markdownEditor").value = htmlToMarkdown($("visualEditor").innerHTML);
    }
}

function captureEditorScrollRatio(mode) {
    const element = mode === "preview" ? $("previewFrame") : $("markdownEditor");
    const maxScroll = element.scrollHeight - element.clientHeight;
    if (maxScroll <= 0) {
        return 0;
    }
    return element.scrollTop / maxScroll;
}

function applyEditorScrollRatio(mode, ratio) {
    window.requestAnimationFrame(() => {
        const element = mode === "preview" ? $("previewFrame") : $("markdownEditor");
        const maxScroll = element.scrollHeight - element.clientHeight;
        element.scrollTop = Math.max(0, maxScroll * ratio);
        element.focus({preventScroll: true});
    });
}

function syncRawFromPreview() {
    if (state.editorMode === "preview") {
        $("markdownEditor").value = htmlToMarkdown(sanitizedEditableHtml($("previewBody")));
    }
}

function insertMarkdown(markdown) {
    syncRawFromActiveEditor();
    if (state.editorMode === "raw") {
        insertIntoTextarea($("markdownEditor"), markdown);
    } else if (state.editorMode === "preview") {
        setEditorMode("preview");
    }
}

function insertMedia(url, name) {
    const media = mediaHtml(url, name);
    if (state.editorMode === "preview") {
        restoreEditorSelection();
        insertIntoEditable($("previewBody"), media);
        enhancePreviewMediaBlocks();
        syncRawFromPreview();
        rememberEditorSelection();
        return;
    }
    insertIntoTextarea($("markdownEditor"), `\n\n${media}\n\n`);
}

function mediaHtml(url, name) {
    return `<figure class="blog-media-block"><img src="${escapeHtml(url)}" alt="${escapeHtml(name)}" loading="lazy" decoding="async"><figcaption>${escapeHtml(name)}</figcaption></figure>`;
}

function insertStyleSnippet(name) {
    const snippet = STYLE_SNIPPETS[name];
    if (snippet) {
        insertHtmlSnippet(snippet);
    }
}

function insertHtmlSnippet(snippet) {
    if (state.editorMode === "raw") {
        insertIntoTextarea($("markdownEditor"), `\n\n${snippet}\n\n`);
        return;
    }
    const target = state.editorMode === "preview" ? $("previewBody") : $("visualEditor");
    restoreEditorSelection();
    insertIntoEditable(target, snippet);
    syncRawFromActiveEditor();
    if (state.editorMode === "visual") {
        $("visualEditor").focus();
    }
    if (state.editorMode === "preview") {
        renderPreview({
            title: $("titleInput").value.trim() || "Article",
            date: $("dateInput").value,
            categories: textToList($("categoriesInput").value),
            content: $("markdownEditor").value,
        });
        $("previewBody").focus();
    }
}

function insertIntoEditable(target, html) {
    target.focus();
    const selection = window.getSelection();
    if (selection && selection.rangeCount && target.contains(selection.anchorNode)) {
        document.execCommand("insertHTML", false, html);
        return;
    }
    target.insertAdjacentHTML("beforeend", html);
}

function applyRawToolbar(command, value) {
    const textarea = $("markdownEditor");
    if (command === "bold") {
        wrapTextareaSelection(textarea, "**", "**", "texte");
    } else if (command === "italic") {
        wrapTextareaSelection(textarea, "*", "*", "texte");
    } else if (command === "formatBlock" && value === "blockquote") {
        prefixTextareaLines(textarea, "> ");
    } else if (command === "formatBlock") {
        prefixTextareaLines(textarea, value === "h3" ? "### " : value === "h1" ? "# " : "## ");
    } else if (command === "insertUnorderedList") {
        prefixTextareaLines(textarea, "- ");
    }
}

function wrapTextareaSelection(textarea, prefix, suffix, fallback) {
    const start = textarea.selectionStart || 0;
    const end = textarea.selectionEnd || 0;
    const selected = textarea.value.slice(start, end) || fallback;
    const replacement = `${prefix}${selected}${suffix}`;
    textarea.value = textarea.value.slice(0, start) + replacement + textarea.value.slice(end);
    textarea.selectionStart = start + prefix.length;
    textarea.selectionEnd = start + prefix.length + selected.length;
    textarea.focus();
}

function prefixTextareaLines(textarea, prefix) {
    const start = textarea.selectionStart || 0;
    const end = textarea.selectionEnd || 0;
    const selected = textarea.value.slice(start, end) || "texte";
    const replacement = selected
        .split("\n")
        .map(line => line.trim() ? `${prefix}${line}` : line)
        .join("\n");
    textarea.value = textarea.value.slice(0, start) + replacement + textarea.value.slice(end);
    textarea.selectionStart = start;
    textarea.selectionEnd = start + replacement.length;
    textarea.focus();
}

function insertIntoTextarea(textarea, text) {
    const start = textarea.selectionStart || textarea.value.length;
    const end = textarea.selectionEnd || textarea.value.length;
    textarea.value = textarea.value.slice(0, start) + text + textarea.value.slice(end);
    textarea.selectionStart = textarea.selectionEnd = start + text.length;
    textarea.focus();
}

function activeEditable() {
    if (state.editorMode === "preview") {
        return $("previewBody");
    }
    if (state.editorMode === "visual") {
        return $("visualEditor");
    }
    return null;
}

function rememberEditorSelection() {
    const target = activeEditable();
    if (!target) {
        return;
    }
    const selection = window.getSelection();
    if (!selection || !selection.rangeCount) {
        return;
    }
    const range = selection.getRangeAt(0);
    if (target.contains(range.startContainer) && target.contains(range.endContainer)) {
        state.editorSelection = range.cloneRange();
    }
}

function restoreEditorSelection() {
    const target = activeEditable();
    if (!target) {
        return;
    }
    target.focus();
    const selection = window.getSelection();
    if (selection && state.editorSelection && target.contains(state.editorSelection.startContainer) && target.contains(state.editorSelection.endContainer)) {
        selection.removeAllRanges();
        selection.addRange(state.editorSelection);
        return;
    }
    moveCaretToEnd(target);
}

function moveCaretToEnd(target) {
    const selection = window.getSelection();
    if (!selection) {
        return;
    }
    const range = document.createRange();
    range.selectNodeContents(target);
    range.collapse(false);
    selection.removeAllRanges();
    selection.addRange(range);
}

function markdownToHtml(markdown) {
    const blocks = markdown.split(/\n{2,}/);
    return blocks.map((block) => {
        const trimmed = block.trim();
        if (!trimmed) return "";
        if (/^<[\s\S]*>$/.test(trimmed)) return trimmed;
        if (/^###\s+/.test(trimmed)) return `<h3>${inlineMarkdown(trimmed.replace(/^###\s+/, ""))}</h3>`;
        if (/^##\s+/.test(trimmed)) return `<h2>${inlineMarkdown(trimmed.replace(/^##\s+/, ""))}</h2>`;
        if (/^#\s+/.test(trimmed)) return `<h1>${inlineMarkdown(trimmed.replace(/^#\s+/, ""))}</h1>`;
        if (/^>\s*/.test(trimmed)) return `<blockquote>${inlineMarkdown(trimmed.replace(/^>\s*/gm, ""))}</blockquote>`;
        if (/^[-*]\s+/m.test(trimmed)) {
            const items = trimmed.split(/\n/).filter(Boolean).map((line) => `<li>${inlineMarkdown(line.replace(/^[-*]\s+/, ""))}</li>`);
            return `<ul>${items.join("")}</ul>`;
        }
        const image = trimmed.match(/^!\[([^\]]*)\]\(([^)]+)\)$/);
        if (image) return `<p><img src="${escapeHtml(image[2])}" alt="${escapeHtml(image[1])}"></p>`;
        return `<p>${inlineMarkdown(trimmed).replace(/\n/g, "<br>")}</p>`;
    }).join("");
}

function renderPreview(article) {
    const categoryText = article.categories.join(", ");
    $("previewTitle").textContent = article.title;
    $("previewMeta").textContent = `${normalizeDate(article.date)}${categoryText ? " · " + categoryText : ""}`;
    $("previewBody").innerHTML = markdownToHtml(article.content);
    enhancePreviewMediaBlocks();
}

function enhancePreviewMediaBlocks() {
    const preview = $("previewBody");
    preview.querySelectorAll(".blog-media-block").forEach((block) => {
        block.setAttribute("draggable", "true");
        block.setAttribute("contenteditable", "false");
    });

    if (preview.dataset.mediaDraggingReady) {
        return;
    }
    preview.dataset.mediaDraggingReady = "true";
    preview.addEventListener("dragstart", (event) => {
        const block = event.target.closest(".blog-media-block");
        if (!block || !preview.contains(block)) {
            return;
        }
        state.draggedMedia = block;
        block.classList.add("is-dragging");
        if (event.dataTransfer) {
            event.dataTransfer.effectAllowed = "move";
            event.dataTransfer.setData("text/plain", "");
        }
    });
    preview.addEventListener("dragend", () => {
        if (state.draggedMedia) {
            state.draggedMedia.classList.remove("is-dragging");
        }
        state.draggedMedia = null;
        syncRawFromPreview();
    });
    preview.addEventListener("dragover", (event) => {
        if (!state.draggedMedia) {
            return;
        }
        event.preventDefault();
        if (event.dataTransfer) {
            event.dataTransfer.dropEffect = "move";
        }
        const target = closestMovableBlock(event.target);
        if (!target || target === state.draggedMedia) {
            return;
        }
        const box = target.getBoundingClientRect();
        if (event.clientY > box.top + box.height / 2) {
            target.after(state.draggedMedia);
        } else {
            target.before(state.draggedMedia);
        }
    });
    preview.addEventListener("drop", (event) => {
        if (!state.draggedMedia) {
            return;
        }
        event.preventDefault();
        state.draggedMedia.classList.remove("is-dragging");
        state.draggedMedia = null;
        syncRawFromPreview();
    });
}

function closestMovableBlock(node) {
    const element = node.nodeType === Node.ELEMENT_NODE ? node : node.parentElement;
    if (!element) {
        return null;
    }
    const block = element.closest(".blog-media-block, p, h1, h2, h3, blockquote, ul, ol, figure, div");
    if (!block || !$("previewBody").contains(block) || block === $("previewBody")) {
        return null;
    }
    return block;
}

function inlineMarkdown(value) {
    return escapeHtml(value)
        .replace(/\*\*([^*]+)\*\*/g, "<strong>$1</strong>")
        .replace(/\*([^*]+)\*/g, "<em>$1</em>")
        .replace(/\[([^\]]+)\]\(([^)]+)\)/g, '<a href="$2">$1</a>');
}

function htmlToMarkdown(html) {
    const container = document.createElement("div");
    container.innerHTML = html;
    return [...container.childNodes].map(nodeToMarkdown).join("\n\n").replace(/\n{3,}/g, "\n\n").trim() + "\n";
}

function sanitizedEditableHtml(element) {
    const clone = element.cloneNode(true);
    clone.querySelectorAll("[draggable]").forEach((node) => node.removeAttribute("draggable"));
    clone.querySelectorAll("[contenteditable]").forEach((node) => node.removeAttribute("contenteditable"));
    clone.querySelectorAll("[data-media-dragging-ready]").forEach((node) => node.removeAttribute("data-media-dragging-ready"));
    clone.querySelectorAll(".is-dragging").forEach((node) => node.classList.remove("is-dragging"));
    return clone.innerHTML;
}

function nodeToMarkdown(node) {
    if (node.nodeType === Node.TEXT_NODE) return node.textContent;
    if (node.nodeType !== Node.ELEMENT_NODE) return "";
    const tag = node.tagName.toLowerCase();
    if (shouldKeepHtml(node, tag)) return node.outerHTML;
    const inner = [...node.childNodes].map(inlineNodeToMarkdown).join("").trim();
    if (tag === "h1") return `# ${inner}`;
    if (tag === "h2") return `## ${inner}`;
    if (tag === "h3") return `### ${inner}`;
    if (tag === "blockquote") return inner.split("\n").map(line => `> ${line}`).join("\n");
    if (tag === "ul") return [...node.children].map(li => `- ${[...li.childNodes].map(inlineNodeToMarkdown).join("").trim()}`).join("\n");
    if (tag === "ol") return [...node.children].map((li, i) => `${i + 1}. ${[...li.childNodes].map(inlineNodeToMarkdown).join("").trim()}`).join("\n");
    if (tag === "p" || tag === "div") return inner;
    return inner;
}

function inlineNodeToMarkdown(node) {
    if (node.nodeType === Node.TEXT_NODE) return node.textContent;
    if (node.nodeType !== Node.ELEMENT_NODE) return "";
    const tag = node.tagName.toLowerCase();
    if (shouldKeepHtml(node, tag)) return node.outerHTML;
    const inner = [...node.childNodes].map(inlineNodeToMarkdown).join("");
    if (tag === "strong" || tag === "b") return `**${inner}**`;
    if (tag === "em" || tag === "i") return `*${inner}*`;
    if (tag === "a") return `[${inner}](${node.getAttribute("href") || ""})`;
    if (tag === "br") return "\n";
    if (tag === "img") return `![${node.getAttribute("alt") || "image"}](${node.getAttribute("src") || ""})`;
    return inner;
}

function shouldKeepHtml(node, tag) {
    return ["span", "figure", "figcaption"].includes(tag)
        || node.hasAttribute("class")
        || node.hasAttribute("style")
        || node.hasAttribute("id")
        || (["p", "div"].includes(tag) && node.querySelector("[style], [class], img, figure"));
}

function cleanMarkdown(value) {
    return cleanTextFormatting(value)
        .replace(/\n{3,}/g, "\n\n")
        .trim() + "\n";
}

function cleanTextFormatting(value) {
    return String(value || "")
        .replace(/<span[^>]*>/gi, "")
        .replace(/<\/span>/gi, "")
        .replace(/\s+(style|class|id)="[^"]*"/gi, "")
        .replace(/\*\*([^*]+)\*\*/g, "$1")
        .replace(/\*([^*]+)\*/g, "$1")
        .replace(/\[([^\]]+)\]\([^)]+\)/g, "$1");
}

function textToList(value) {
    return value.split(",").map(item => item.trim()).filter(Boolean);
}

function listToText(value) {
    return Array.isArray(value) ? value.join(", ") : (value || "");
}

function normalizeDate(value) {
    const match = String(value).match(/\d{4}-\d{2}-\d{2}/);
    return match ? match[0] : new Date().toISOString().slice(0, 10);
}

function formatArticleDate(value) {
    const normalized = normalizeDate(value);
    const date = new Date(`${normalized}T00:00:00`);
    if (Number.isNaN(date.getTime())) {
        return normalized;
    }
    return new Intl.DateTimeFormat("fr-FR", {
        weekday: "short",
        day: "2-digit",
        month: "short",
        year: "numeric",
    }).format(date);
}

function defaultGitChecked(path) {
    return /^(content|static|layouts|data|blog-manager|hugo\.toml|\.gitignore)/.test(path);
}

function formatCommandResult(result) {
    return `$ ${result.command.join(" ")}\nexit ${result.code}\n${result.stdout || ""}${result.stderr || ""}`;
}

function escapeHtml(value) {
    return String(value || "").replace(/[&<>"']/g, (char) => ({
        "&": "&amp;",
        "<": "&lt;",
        ">": "&gt;",
        '"': "&quot;",
        "'": "&#039;",
    }[char]));
}

function setupAutocomplete(inputId, suggestionsId, getOptions) {
    const input = $(inputId);
    const suggestions = $(suggestionsId);

    function currentToken() {
        const parts = input.value.split(",");
        return parts[parts.length - 1].trim();
    }

    function applySuggestion(value) {
        const parts = input.value.split(",");
        parts[parts.length - 1] = ` ${value}`;
        input.value = parts.map((part, index) => index === 0 ? part.trim() : part.trim()).filter(Boolean).join(", ");
        suggestions.hidden = true;
        input.focus();
    }

    function renderSuggestions() {
        const token = currentToken().toLowerCase();
        const selected = new Set(textToList(input.value).map(value => value.toLowerCase()));
        const matches = getOptions()
            .filter((option) => !selected.has(option.toLowerCase()) || option.toLowerCase() === token)
            .filter((option) => !token || option.toLowerCase().includes(token))
            .slice(0, 10);

        if (!matches.length) {
            suggestions.hidden = true;
            suggestions.innerHTML = "";
            return;
        }

        suggestions.innerHTML = matches.map((option) => (
            `<button type="button" data-value="${escapeHtml(option)}">${escapeHtml(option)}</button>`
        )).join("");
        suggestions.hidden = false;
    }

    input.addEventListener("input", renderSuggestions);
    input.addEventListener("focus", renderSuggestions);
    input.addEventListener("blur", () => window.setTimeout(() => suggestions.hidden = true, 120));
    input.addEventListener("keydown", (event) => {
        const first = suggestions.querySelector("button");
        if (!suggestions.hidden && first && (event.key === "Tab" || event.key === "Enter")) {
            event.preventDefault();
            applySuggestion(first.dataset.value);
        }
        if (event.key === "Escape") {
            suggestions.hidden = true;
        }
    });
    suggestions.addEventListener("mousedown", (event) => {
        event.preventDefault();
        const button = event.target.closest("button");
        if (button) {
            applySuggestion(button.dataset.value);
        }
    });
}

function bindEvents() {
    $("searchInput").addEventListener("input", renderArticleList);
    $("newArticleButton").addEventListener("click", newArticle);
    $("saveButton").addEventListener("click", () => saveArticle().catch(error => log(error.message)));
    $("docxInput").addEventListener("change", event => event.target.files[0] && importDocx(event.target.files[0]).catch(error => log(error.message)));
    $("mediaInput").addEventListener("change", event => event.target.files[0] && importMedia(event.target.files[0]).catch(error => log(error.message)));
    $("homepageButton").addEventListener("click", () => setHomepage(false).catch(error => log(error.message)));
    $("homepageDefaultButton").addEventListener("click", () => setHomepage(true).catch(error => log(error.message)));
    $("buildButton").addEventListener("click", () => buildSite().catch(error => log(error.message)));
    $("gitRefreshButton").addEventListener("click", () => refreshGit().catch(error => log(error.message)));
    $("previewButton").addEventListener("click", previewArticle);
    $("closeGitButton").addEventListener("click", () => $("gitPanel").hidden = true);
    $("commitButton").addEventListener("click", () => commitPush().catch(error => log(error.message)));
    $("codeModeButton").dataset.modeButton = "raw";
    $("previewModeButton").dataset.modeButton = "preview";
    $("codeModeButton").addEventListener("click", () => setEditorMode("raw"));
    $("previewModeButton").addEventListener("click", previewArticle);
    $("linkButton").addEventListener("click", createLink);
    $("cleanButton").addEventListener("click", cleanFormatting);
    document.querySelector(".toolbar").addEventListener("mousedown", (event) => {
        if (event.target.closest("button")) {
            event.preventDefault();
        }
    });
    document.querySelectorAll(".toolbar [data-command]").forEach(button => {
        button.addEventListener("click", () => applyToolbar(button));
    });
    document.querySelectorAll(".toolbar [data-snippet]").forEach(button => {
        button.addEventListener("click", () => insertStyleSnippet(button.dataset.snippet));
    });
    $("visualEditor").addEventListener("input", () => {
        syncRawFromVisual();
        rememberEditorSelection();
    });
    $("visualEditor").addEventListener("keyup", rememberEditorSelection);
    $("visualEditor").addEventListener("mouseup", rememberEditorSelection);
    $("previewBody").addEventListener("input", () => {
        syncRawFromPreview();
        rememberEditorSelection();
    });
    $("previewBody").addEventListener("keyup", rememberEditorSelection);
    $("previewBody").addEventListener("mouseup", rememberEditorSelection);
    $("markdownEditor").addEventListener("input", () => {
        if (!state.rawMode) return;
    });
    document.addEventListener("selectionchange", rememberEditorSelection);
    setupAutocomplete("categoriesInput", "categoriesSuggestions", () => state.categoryOptions);
    setupAutocomplete("tagsInput", "tagsSuggestions", () => state.tagOptions);
}

bindEvents();
refreshArticles().catch(error => log(error.message));
