(function () {
    function escapeHtml(value) {
        return String(value || "").replace(/[&<>"']/g, function (char) {
            return {
                "&": "&amp;",
                "<": "&lt;",
                ">": "&gt;",
                '"': "&quot;",
                "'": "&#039;"
            }[char];
        });
    }

    function formatDate(value) {
        var date = new Date(value);
        if (Number.isNaN(date.getTime())) {
            return "";
        }
        return new Intl.DateTimeFormat("fr-FR", {
            day: "2-digit",
            month: "long",
            year: "numeric"
        }).format(date);
    }

    function updateMetaCount(count) {
        var meta = document.querySelector(".comments-link");
        if (!meta) {
            return;
        }
        meta.textContent = count + " commentaire" + (count > 1 ? "s" : "");
    }

    function renderComments(root, comments) {
        var list = root.querySelector("[data-mdj-comments-list]");
        if (!comments.length) {
            list.innerHTML = '<p class="mdj-comments-empty">Aucun commentaire pour le moment.</p>';
            updateMetaCount(0);
            return;
        }

        list.innerHTML = comments.map(function (comment) {
            var author = escapeHtml(comment.author_name);
            var authorHtml = comment.author_url
                ? '<a href="' + escapeHtml(comment.author_url) + '" rel="nofollow noopener" target="_blank">' + author + "</a>"
                : author;
            var content = escapeHtml(comment.content).replace(/\n/g, "<br>");
            return '<article class="mdj-comment">' +
                '<header class="mdj-comment-header">' +
                '<strong class="mdj-comment-author">' + authorHtml + '</strong>' +
                '<time class="mdj-comment-date" datetime="' + escapeHtml(comment.created_at) + '">' + escapeHtml(formatDate(comment.created_at)) + '</time>' +
                '</header>' +
                '<div class="mdj-comment-content">' + content + '</div>' +
                '</article>';
        }).join("");
        updateMetaCount(comments.length);
    }

    function setStatus(root, message, kind) {
        var node = root.querySelector("[data-mdj-comments-status]");
        node.textContent = message || "";
        node.className = "mdj-comments-status" + (kind ? " mdj-comments-status-" + kind : "");
    }

    function loadComments(root) {
        var endpoint = root.dataset.endpoint;
        var postPath = root.dataset.postPath;
        var url = endpoint + "?post_path=" + encodeURIComponent(postPath);

        fetch(url, {
            method: "GET",
            credentials: "omit",
            headers: {
                "Accept": "application/json"
            }
        })
            .then(function (response) {
                if (!response.ok) {
                    throw new Error("Impossible de charger les commentaires.");
                }
                return response.json();
            })
            .then(function (payload) {
                renderComments(root, payload.comments || []);
            })
            .catch(function () {
                root.querySelector("[data-mdj-comments-list]").innerHTML =
                    '<p class="mdj-comments-empty">Les commentaires sont indisponibles pour le moment.</p>';
            });
    }

    function submitComment(root, form) {
        var endpoint = root.dataset.endpoint;
        var body = new URLSearchParams(new FormData(form));
        body.set("post_path", root.dataset.postPath);
        body.set("post_title", root.dataset.postTitle);

        var button = form.querySelector("button[type=submit]");
        button.disabled = true;
        setStatus(root, "Envoi du commentaire...", "");

        fetch(endpoint, {
            method: "POST",
            credentials: "omit",
            headers: {
                "Accept": "application/json",
                "Content-Type": "application/x-www-form-urlencoded;charset=UTF-8"
            },
            body: body.toString()
        })
            .then(function (response) {
                return response.json().then(function (payload) {
                    if (!response.ok) {
                        throw new Error(payload.message || "Le commentaire n'a pas pu etre envoye.");
                    }
                    return payload;
                });
            })
            .then(function (payload) {
                form.reset();
                form.querySelector("[name=created_at]").value = Math.floor(Date.now() / 1000);
                setStatus(root, payload.message || "Merci. Votre commentaire est en attente de validation.", "success");
                loadComments(root);
            })
            .catch(function (error) {
                setStatus(root, error.message, "error");
            })
            .finally(function () {
                button.disabled = false;
            });
    }

    function init(root) {
        var form = root.querySelector("[data-mdj-comments-form]");
        form.querySelector("[name=created_at]").value = Math.floor(Date.now() / 1000);
        form.addEventListener("submit", function (event) {
            event.preventDefault();
            submitComment(root, form);
        });
        loadComments(root);
    }

    document.addEventListener("DOMContentLoaded", function () {
        document.querySelectorAll("[data-mdj-comments]").forEach(init);
    });
}());
