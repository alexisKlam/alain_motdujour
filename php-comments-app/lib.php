<?php

declare(strict_types=1);

const MDJ_STATUSES = ['pending', 'approved', 'spam', 'trash'];
const MDJ_RULE_FIELDS = ['content', 'author_name', 'author_email', 'author_url', 'user_ip'];
const MDJ_RULE_MATCH_TYPES = ['contains', 'regex', 'email_domain', 'equals'];
const MDJ_RULE_ACTIONS = ['reject', 'hold', 'approve'];

function mdj_config(): array
{
    static $config;
    if ($config !== null) {
        return $config;
    }

    $path = __DIR__ . '/config.php';
    if (!is_file($path)) {
        mdj_json(['message' => 'Missing config.php. Copy config.sample.php to config.php first.'], 500);
    }

    $config = require $path;
    if (!is_array($config)) {
        mdj_json(['message' => 'Invalid config.php.'], 500);
    }

    return $config;
}

function mdj_pdo(): PDO
{
    static $pdo;
    if ($pdo instanceof PDO) {
        return $pdo;
    }

    $db = mdj_config()['db'] ?? [];
    $pdo = new PDO($db['dsn'] ?? '', $db['user'] ?? '', $db['password'] ?? '', [
        PDO::ATTR_ERRMODE => PDO::ERRMODE_EXCEPTION,
        PDO::ATTR_DEFAULT_FETCH_MODE => PDO::FETCH_ASSOC,
        PDO::ATTR_EMULATE_PREPARES => false,
    ]);
    return $pdo;
}

function mdj_json(array $payload, int $status = 200): void
{
    http_response_code($status);
    header('Content-Type: application/json; charset=utf-8');
    echo json_encode($payload, JSON_UNESCAPED_UNICODE | JSON_UNESCAPED_SLASHES);
    exit;
}

function mdj_wants_json(): bool
{
    return strpos($_SERVER['HTTP_ACCEPT'] ?? '', 'application/json') !== false;
}

function mdj_clean_string(string $value, int $max = 255): string
{
    $value = trim(strip_tags($value));
    $value = preg_replace('/[[:cntrl:]]+/u', '', $value) ?? '';
    return substr($value, 0, $max);
}

function mdj_clean_text(string $value, int $max = 4000): string
{
    $value = trim(strip_tags($value));
    $value = preg_replace("/\r\n|\r/u", "\n", $value) ?? '';
    return substr($value, 0, $max);
}

function mdj_post_path(string $value): string
{
    $path = parse_url($value, PHP_URL_PATH);
    $path = $path !== false && $path !== null ? $path : $value;
    return mdj_clean_string('/' . ltrim($path, '/'), 255);
}

function mdj_remote_ip(): string
{
    foreach (['HTTP_CF_CONNECTING_IP', 'HTTP_X_FORWARDED_FOR', 'REMOTE_ADDR'] as $key) {
        if (empty($_SERVER[$key])) {
            continue;
        }
        $ip = trim(explode(',', (string) $_SERVER[$key])[0]);
        if (filter_var($ip, FILTER_VALIDATE_IP)) {
            return $ip;
        }
    }
    return '';
}

function mdj_allowed_origin(?string $origin): bool
{
    if (!$origin) {
        return true;
    }

    $allowed = mdj_config()['allowed_origins'] ?? [];
    return in_array(rtrim($origin, '/'), array_map(static fn($item) => rtrim((string) $item, '/'), $allowed), true);
}

function mdj_cors(): void
{
    $origin = $_SERVER['HTTP_ORIGIN'] ?? '';
    if ($origin !== '' && mdj_allowed_origin($origin)) {
        header('Access-Control-Allow-Origin: ' . $origin);
        header('Vary: Origin');
        header('Access-Control-Allow-Methods: GET, POST, OPTIONS');
        header('Access-Control-Allow-Headers: Content-Type, Accept');
    }

    if ($_SERVER['REQUEST_METHOD'] === 'OPTIONS') {
        http_response_code(204);
        exit;
    }
}

function mdj_success_response(string $status = 'pending'): void
{
    mdj_json([
        'message' => mdj_config()['success_message'] ?? 'Merci. Votre commentaire est en attente de validation.',
        'status' => $status,
    ], 202);
}

function mdj_schema_sql(): array
{
    return [
        "CREATE TABLE IF NOT EXISTS mdj_comments (
            id BIGINT UNSIGNED NOT NULL AUTO_INCREMENT,
            post_path VARCHAR(255) NOT NULL,
            post_title VARCHAR(255) NOT NULL DEFAULT '',
            author_name VARCHAR(120) NOT NULL,
            author_email VARCHAR(190) NOT NULL DEFAULT '',
            author_url VARCHAR(255) NOT NULL DEFAULT '',
            content TEXT NOT NULL,
            status VARCHAR(20) NOT NULL DEFAULT 'pending',
            moderation_reason VARCHAR(255) NOT NULL DEFAULT '',
            user_ip VARCHAR(45) NOT NULL DEFAULT '',
            user_agent VARCHAR(255) NOT NULL DEFAULT '',
            created_at DATETIME NOT NULL,
            updated_at DATETIME NOT NULL,
            PRIMARY KEY (id),
            KEY post_status (post_path, status),
            KEY status_created (status, created_at)
        ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci",
        "CREATE TABLE IF NOT EXISTS mdj_comment_rules (
            id BIGINT UNSIGNED NOT NULL AUTO_INCREMENT,
            label VARCHAR(120) NOT NULL DEFAULT '',
            field VARCHAR(40) NOT NULL,
            match_type VARCHAR(40) NOT NULL,
            pattern VARCHAR(255) NOT NULL,
            action VARCHAR(20) NOT NULL,
            enabled TINYINT(1) NOT NULL DEFAULT 1,
            created_at DATETIME NOT NULL,
            PRIMARY KEY (id),
            KEY enabled_action (enabled, action)
        ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci",
    ];
}

function mdj_rule_matches(string $value, string $match_type, string $pattern): bool
{
    $value_lower = strtolower($value);
    $pattern_lower = strtolower($pattern);

    if ($match_type === 'contains') {
        return $pattern_lower !== '' && strpos($value_lower, $pattern_lower) !== false;
    }

    if ($match_type === 'equals') {
        return $value_lower === $pattern_lower;
    }

    if ($match_type === 'email_domain') {
        $domain = substr(strrchr($value_lower, '@') ?: '', 1);
        return $domain !== '' && $domain === ltrim($pattern_lower, '@');
    }

    if ($match_type === 'regex') {
        return $pattern !== '' && @preg_match('/' . str_replace('/', '\/', $pattern) . '/iu', $value) === 1;
    }

    return false;
}

function mdj_moderate(array $comment): array
{
    $stmt = mdj_pdo()->query('SELECT * FROM mdj_comment_rules WHERE enabled = 1 ORDER BY id ASC');
    foreach ($stmt->fetchAll() as $rule) {
        $field = (string) $rule['field'];
        $value = isset($comment[$field]) ? (string) $comment[$field] : '';
        if (mdj_rule_matches($value, (string) $rule['match_type'], (string) $rule['pattern'])) {
            return [
                'action' => (string) $rule['action'],
                'reason' => $rule['label'] ?: ($rule['field'] . ' ' . $rule['match_type'] . ' ' . $rule['pattern']),
            ];
        }
    }

    return ['action' => 'hold', 'reason' => ''];
}

function mdj_require_admin(): void
{
    session_start();
    if (!empty($_SESSION['mdj_admin'])) {
        return;
    }

    if ($_SERVER['REQUEST_METHOD'] === 'POST' && isset($_POST['password'])) {
        $hash = mdj_config()['admin']['password_hash'] ?? '';
        if (is_string($hash) && password_verify((string) $_POST['password'], $hash)) {
            $_SESSION['mdj_admin'] = true;
            header('Location: admin.php');
            exit;
        }
        $GLOBALS['mdj_login_error'] = 'Mot de passe incorrect.';
        return;
    }
}

function mdj_admin_logged_in(): bool
{
    return !empty($_SESSION['mdj_admin']);
}

function mdj_html(string $value): string
{
    return htmlspecialchars($value, ENT_QUOTES | ENT_SUBSTITUTE, 'UTF-8');
}
