<?php

declare(strict_types=1);

require __DIR__ . '/lib.php';

mdj_cors();

if ($_SERVER['REQUEST_METHOD'] === 'GET') {
    $post_path = mdj_post_path((string) ($_GET['post_path'] ?? ''));
    if ($post_path === '/') {
        mdj_json(['message' => 'post_path is required.'], 400);
    }

    $stmt = mdj_pdo()->prepare(
        'SELECT id, author_name, author_url, content, created_at
         FROM mdj_comments
         WHERE post_path = :post_path AND status = :status
         ORDER BY created_at ASC'
    );
    $stmt->execute([
        'post_path' => $post_path,
        'status' => 'approved',
    ]);

    $comments = [];
    foreach ($stmt->fetchAll() as $row) {
        $comments[] = [
            'id' => (int) $row['id'],
            'author_name' => $row['author_name'],
            'author_url' => $row['author_url'],
            'content' => $row['content'],
            'created_at' => gmdate('c', strtotime((string) $row['created_at'])),
        ];
    }

    mdj_json([
        'comments' => $comments,
        'count' => count($comments),
    ]);
}

if ($_SERVER['REQUEST_METHOD'] !== 'POST') {
    mdj_json(['message' => 'Method not allowed.'], 405);
}

if (!mdj_allowed_origin($_SERVER['HTTP_ORIGIN'] ?? null)) {
    mdj_json(['message' => 'Origine non autorisee.'], 403);
}

if (trim((string) ($_POST['website_confirm'] ?? '')) !== '') {
    mdj_success_response();
}

$created_at_client = (int) ($_POST['created_at'] ?? 0);
if ($created_at_client > 0 && time() - $created_at_client < 3) {
    mdj_success_response();
}

$comment = [
    'post_path' => mdj_post_path((string) ($_POST['post_path'] ?? '')),
    'post_title' => mdj_clean_string((string) ($_POST['post_title'] ?? ''), 255),
    'author_name' => mdj_clean_string((string) ($_POST['author_name'] ?? ''), 120),
    'author_email' => mdj_clean_string((string) ($_POST['author_email'] ?? ''), 190),
    'author_url' => mdj_clean_string((string) ($_POST['author_url'] ?? ''), 255),
    'content' => mdj_clean_text((string) ($_POST['content'] ?? ''), 4000),
    'user_ip' => mdj_remote_ip(),
    'user_agent' => mdj_clean_string((string) ($_SERVER['HTTP_USER_AGENT'] ?? ''), 255),
];

if ($comment['post_path'] === '/' || $comment['author_name'] === '' || $comment['content'] === '') {
    mdj_json(['message' => 'Nom, commentaire et article sont obligatoires.'], 400);
}

if ($comment['author_email'] !== '' && !filter_var($comment['author_email'], FILTER_VALIDATE_EMAIL)) {
    mdj_json(['message' => 'Adresse e-mail invalide.'], 400);
}

if ($comment['author_url'] !== '' && !filter_var($comment['author_url'], FILTER_VALIDATE_URL)) {
    mdj_json(['message' => 'Adresse de site web invalide.'], 400);
}

$moderation = mdj_moderate($comment);
if ($moderation['action'] === 'reject') {
    mdj_success_response();
}

$status = ($moderation['action'] === 'approve' || !empty(mdj_config()['auto_approve'])) ? 'approved' : 'pending';
$now = gmdate('Y-m-d H:i:s');

$stmt = mdj_pdo()->prepare(
    'INSERT INTO mdj_comments
        (post_path, post_title, author_name, author_email, author_url, content, status, moderation_reason, user_ip, user_agent, created_at, updated_at)
     VALUES
        (:post_path, :post_title, :author_name, :author_email, :author_url, :content, :status, :moderation_reason, :user_ip, :user_agent, :created_at, :updated_at)'
);
$stmt->execute([
    'post_path' => $comment['post_path'],
    'post_title' => $comment['post_title'],
    'author_name' => $comment['author_name'],
    'author_email' => $comment['author_email'],
    'author_url' => $comment['author_url'],
    'content' => $comment['content'],
    'status' => $status,
    'moderation_reason' => $moderation['reason'],
    'user_ip' => $comment['user_ip'],
    'user_agent' => $comment['user_agent'],
    'created_at' => $now,
    'updated_at' => $now,
]);

mdj_success_response($status);
