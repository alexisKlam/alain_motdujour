const state = {
    articles: [],
    activePath: "",
    rawMode: false,
};

const $ = (id) => document.getElementById(id);

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
    renderArticleList();
    $("statusLine").textContent = payload.frontpage?.mode === "manual"
        ? `Premiere page manuelle: ${payload.frontpage.permalink}`
        : "Premiere page: dernier article par date";
    if (!state.activePath && state.articles.length) {
        await loadArticle(state.articles[0].path);
    }
}

function renderArticleList() {
    const query = $("searchInput").value.trim().toLowerCase();
    const items = state.articles.filter((article) => {
        const haystack = `${article.title} ${article.date} ${(article.tags || []).join(" ")} ${article.excerpt}`.toLowerCase();
        return !query || haystack.includes(query);
    });
    $("articleList").innerHTML = items.map((article) => `
        <button class="article-item ${article.path === state.activePath ? "active" : ""}" data-path="${escapeHtml(article.path)}">
            <strong>${escapeHtml(article.title)}</strong>
            <span>${escapeHtml(article.date || "")}</span>
            <span>${escapeHtml(article.excerpt || "")}</span>
        </button>
    `).join("");
    document.querySelectorAll(".article-item").forEach((button) => {
        button.addEventListener("click", () => loadArticle(button.dataset.path));
    });
}

async function loadArticle(path) {
    syncRawFromVisual();
    const article = await api(`/api/article?path=${encodeURIComponent(path)}`);
    state.activePath = article.path;
    $("titleInput").value = article.meta.title || "";
    $("dateInput").value = normalizeDate(article.meta.date || "");
    $("categoriesInput").value = listToText(article.meta.categories);
    $("tagsInput").value = listToText(article.meta.tags);
    $("authorInput").value = article.meta.author || "alain";
    $("markdownEditor").value = article.content || "";
    $("visualEditor").innerHTML = markdownToHtml(article.content || "");
    $("screenTitle").textContent = article.meta.title || "Editeur";
    renderArticleList();
}

function newArticle() {
    const today = new Date().toISOString().slice(0, 10);
    state.activePath = "";
    $("titleInput").value = `Article du ${today}`;
    $("dateInput").value = today;
    $("categoriesInput").value = "Mot du jour";
    $("tagsInput").value = "";
    $("authorInput").value = "alain";
    $("markdownEditor").value = "";
    $("visualEditor").innerHTML = "<p></p>";
    $("screenTitle").textContent = "Nouvel article";
    renderArticleList();
}

async function saveArticle() {
    syncRawFromVisual();
    const dateValue = $("dateInput").value || new Date().toISOString().slice(0, 10);
    const payload = {
        path: state.activePath,
        meta: {
            title: $("titleInput").value.trim() || "Nouvel article",
            author: $("authorInput").value.trim() || "alain",
            type: "post",
            date: `${dateValue}T00:00:00+00:00`,
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
    insertMarkdown(`\n\n![${file.name}](${result.url})\n\n`);
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
    if (state.rawMode) {
        return;
    }
    const command = button.dataset.command;
    const value = button.dataset.value || null;
    document.execCommand(command, false, value);
    syncRawFromVisual();
}

function createLink() {
    const url = window.prompt("URL du lien");
    if (!url) {
        return;
    }
    document.execCommand("createLink", false, url);
    syncRawFromVisual();
}

function cleanFormatting() {
    if (state.rawMode) {
        $("markdownEditor").value = cleanMarkdown($("markdownEditor").value);
        return;
    }
    document.execCommand("removeFormat", false, null);
    syncRawFromVisual();
}

function toggleRaw() {
    const shell = document.querySelector(".editor-shell");
    if (state.rawMode) {
        $("visualEditor").innerHTML = markdownToHtml($("markdownEditor").value);
        state.rawMode = false;
        shell.classList.remove("raw");
    } else {
        syncRawFromVisual();
        state.rawMode = true;
        shell.classList.add("raw");
    }
}

function syncRawFromVisual() {
    if (!state.rawMode) {
        $("markdownEditor").value = htmlToMarkdown($("visualEditor").innerHTML);
    }
}

function insertMarkdown(markdown) {
    syncRawFromVisual();
    $("markdownEditor").value += markdown;
    if (!state.rawMode) {
        $("visualEditor").innerHTML = markdownToHtml($("markdownEditor").value);
    }
}

function markdownToHtml(markdown) {
    const blocks = markdown.split(/\n{2,}/);
    return blocks.map((block) => {
        const trimmed = block.trim();
        if (!trimmed) return "";
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

function nodeToMarkdown(node) {
    if (node.nodeType === Node.TEXT_NODE) return node.textContent;
    if (node.nodeType !== Node.ELEMENT_NODE) return "";
    const tag = node.tagName.toLowerCase();
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
    const inner = [...node.childNodes].map(inlineNodeToMarkdown).join("");
    if (tag === "strong" || tag === "b") return `**${inner}**`;
    if (tag === "em" || tag === "i") return `*${inner}*`;
    if (tag === "a") return `[${inner}](${node.getAttribute("href") || ""})`;
    if (tag === "br") return "\n";
    if (tag === "img") return `![${node.getAttribute("alt") || "image"}](${node.getAttribute("src") || ""})`;
    return inner;
}

function cleanMarkdown(value) {
    return value
        .replace(/<span[^>]*>/gi, "")
        .replace(/<\/span>/gi, "")
        .replace(/\n{3,}/g, "\n\n")
        .trim() + "\n";
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
    $("closeGitButton").addEventListener("click", () => $("gitPanel").hidden = true);
    $("commitButton").addEventListener("click", () => commitPush().catch(error => log(error.message)));
    $("toggleMarkdownButton").addEventListener("click", toggleRaw);
    $("linkButton").addEventListener("click", createLink);
    $("cleanButton").addEventListener("click", cleanFormatting);
    document.querySelectorAll(".toolbar [data-command]").forEach(button => {
        button.addEventListener("click", () => applyToolbar(button));
    });
    $("visualEditor").addEventListener("input", syncRawFromVisual);
    $("markdownEditor").addEventListener("input", () => {
        if (!state.rawMode) return;
    });
}

bindEvents();
refreshArticles().catch(error => log(error.message));
