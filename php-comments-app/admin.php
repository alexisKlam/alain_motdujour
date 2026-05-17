<?php

declare(strict_types=1);

require __DIR__ . '/lib.php';

mdj_require_admin();

if (!mdj_admin_logged_in()):
?>
<!doctype html>
<html lang="fr">
<head>
    <meta charset="utf-8">
    <meta name="viewport" content="width=device-width, initial-scale=1">
    <title>Administration commentaires MDJ</title>
    <link rel="stylesheet" href="admin.css">
</head>
<body class="mdj-admin-login">
    <main class="mdj-admin-box">
        <h1>Commentaires MDJ</h1>
        <?php if (!empty($GLOBALS['mdj_login_error'])): ?>
            <p class="mdj-alert mdj-alert-error"><?php echo mdj_html($GLOBALS['mdj_login_error']); ?></p>
        <?php endif; ?>
        <form method="post">
            <label>
                Mot de passe
                <input name="password" type="password" autocomplete="current-password" required>
            </label>
            <button type="submit">Se connecter</button>
        </form>
    </main>
</body>
</html>
<?php
exit;
endif;

if (empty($_SESSION['mdj_csrf'])) {
    $_SESSION['mdj_csrf'] = bin2hex(random_bytes(16));
}

$message = '';
$status = in_array((string) ($_GET['status'] ?? 'pending'), MDJ_STATUSES, true) ? (string) $_GET['status'] : 'pending';

if ($_SERVER['REQUEST_METHOD'] === 'POST') {
    if (!hash_equals($_SESSION['mdj_csrf'], (string) ($_POST['csrf'] ?? ''))) {
        http_response_code(403);
        exit('Invalid CSRF token.');
    }

    $action = (string) ($_POST['action'] ?? '');
    $id = (int) ($_POST['id'] ?? 0);
    $now = gmdate('Y-m-d H:i:s');

    if ($action === 'logout') {
        session_destroy();
        header('Location: admin.php');
        exit;
    }

    if (in_array($action, ['approve_comment', 'spam_comment', 'trash_comment'], true) && $id > 0) {
        $new_status = [
            'approve_comment' => 'approved',
            'spam_comment' => 'spam',
            'trash_comment' => 'trash',
        ][$action];
        $stmt = mdj_pdo()->prepare('UPDATE mdj_comments SET status = :status, updated_at = :updated_at WHERE id = :id');
        $stmt->execute(['status' => $new_status, 'updated_at' => $now, 'id' => $id]);
        $message = 'Commentaire mis a jour.';
    }

    if ($action === 'delete_rule' && $id > 0) {
        $stmt = mdj_pdo()->prepare('DELETE FROM mdj_comment_rules WHERE id = :id');
        $stmt->execute(['id' => $id]);
        $message = 'Regle supprimee.';
    }

    if ($action === 'add_rule') {
        $field = (string) ($_POST['field'] ?? '');
        $match_type = (string) ($_POST['match_type'] ?? '');
        $rule_action = (string) ($_POST['rule_action'] ?? '');
        $pattern = mdj_clean_string((string) ($_POST['pattern'] ?? ''), 255);

        if (
            in_array($field, MDJ_RULE_FIELDS, true)
            && in_array($match_type, MDJ_RULE_MATCH_TYPES, true)
            && in_array($rule_action, MDJ_RULE_ACTIONS, true)
            && $pattern !== ''
        ) {
            $stmt = mdj_pdo()->prepare(
                'INSERT INTO mdj_comment_rules (label, field, match_type, pattern, action, enabled, created_at)
                 VALUES (:label, :field, :match_type, :pattern, :action, 1, :created_at)'
            );
            $stmt->execute([
                'label' => mdj_clean_string((string) ($_POST['label'] ?? ''), 120),
                'field' => $field,
                'match_type' => $match_type,
                'pattern' => $pattern,
                'action' => $rule_action,
                'created_at' => $now,
            ]);
            $message = 'Regle ajoutee.';
        }
    }
}

$counts = array_fill_keys(MDJ_STATUSES, 0);
$count_rows = mdj_pdo()->query('SELECT status, COUNT(*) AS total FROM mdj_comments GROUP BY status')->fetchAll();
foreach ($count_rows as $row) {
    if (isset($counts[$row['status']])) {
        $counts[$row['status']] = (int) $row['total'];
    }
}

$comment_stmt = mdj_pdo()->prepare('SELECT * FROM mdj_comments WHERE status = :status ORDER BY created_at DESC LIMIT 100');
$comment_stmt->execute(['status' => $status]);
$comments = $comment_stmt->fetchAll();
$rules = mdj_pdo()->query('SELECT * FROM mdj_comment_rules ORDER BY enabled DESC, id DESC')->fetchAll();

function mdj_admin_action_button(string $action, int $id, string $label, string $class = ''): void
{
    echo '<form method="post" class="inline-form">';
    echo '<input type="hidden" name="csrf" value="' . mdj_html($_SESSION['mdj_csrf']) . '">';
    echo '<input type="hidden" name="action" value="' . mdj_html($action) . '">';
    echo '<input type="hidden" name="id" value="' . $id . '">';
    echo '<button class="' . mdj_html($class) . '" type="submit">' . mdj_html($label) . '</button>';
    echo '</form>';
}
?>
<!doctype html>
<html lang="fr">
<head>
    <meta charset="utf-8">
    <meta name="viewport" content="width=device-width, initial-scale=1">
    <title>Administration commentaires MDJ</title>
    <link rel="stylesheet" href="admin.css">
</head>
<body>
    <header class="admin-header">
        <h1>Commentaires MDJ</h1>
        <form method="post">
            <input type="hidden" name="csrf" value="<?php echo mdj_html($_SESSION['mdj_csrf']); ?>">
            <button name="action" value="logout" type="submit">Deconnexion</button>
        </form>
    </header>

    <?php if ($message !== ''): ?>
        <p class="mdj-alert"><?php echo mdj_html($message); ?></p>
    <?php endif; ?>

    <nav class="tabs">
        <?php foreach (MDJ_STATUSES as $tab): ?>
            <a class="<?php echo $tab === $status ? 'active' : ''; ?>" href="admin.php?status=<?php echo mdj_html($tab); ?>">
                <?php echo mdj_html($tab); ?> (<?php echo $counts[$tab]; ?>)
            </a>
        <?php endforeach; ?>
    </nav>

    <section>
        <h2>Moderation</h2>
        <table>
            <thead>
                <tr>
                    <th>Date</th>
                    <th>Article</th>
                    <th>Auteur</th>
                    <th>Commentaire</th>
                    <th>Raison</th>
                    <th>Actions</th>
                </tr>
            </thead>
            <tbody>
                <?php if (!$comments): ?>
                    <tr><td colspan="6">Aucun commentaire.</td></tr>
                <?php endif; ?>
                <?php foreach ($comments as $comment): ?>
                    <tr>
                        <td><?php echo mdj_html((string) $comment['created_at']); ?></td>
                        <td>
                            <strong><?php echo mdj_html($comment['post_title'] ?: $comment['post_path']); ?></strong><br>
                            <code><?php echo mdj_html((string) $comment['post_path']); ?></code>
                        </td>
                        <td>
                            <?php echo mdj_html((string) $comment['author_name']); ?><br>
                            <?php if ($comment['author_email']): ?><a href="mailto:<?php echo mdj_html((string) $comment['author_email']); ?>"><?php echo mdj_html((string) $comment['author_email']); ?></a><br><?php endif; ?>
                            <?php if ($comment['author_url']): ?><a href="<?php echo mdj_html((string) $comment['author_url']); ?>" target="_blank" rel="noopener"><?php echo mdj_html((string) $comment['author_url']); ?></a><br><?php endif; ?>
                            <code><?php echo mdj_html((string) $comment['user_ip']); ?></code>
                        </td>
                        <td><?php echo nl2br(mdj_html((string) $comment['content'])); ?></td>
                        <td><?php echo mdj_html((string) $comment['moderation_reason']); ?></td>
                        <td class="actions">
                            <?php mdj_admin_action_button('approve_comment', (int) $comment['id'], 'Valider', 'primary'); ?>
                            <?php mdj_admin_action_button('spam_comment', (int) $comment['id'], 'Spam'); ?>
                            <?php mdj_admin_action_button('trash_comment', (int) $comment['id'], 'Corbeille'); ?>
                        </td>
                    </tr>
                <?php endforeach; ?>
            </tbody>
        </table>
    </section>

    <section>
        <h2>Regles de filtrage</h2>
        <table>
            <thead>
                <tr>
                    <th>Libelle</th>
                    <th>Champ</th>
                    <th>Type</th>
                    <th>Motif</th>
                    <th>Action</th>
                    <th></th>
                </tr>
            </thead>
            <tbody>
                <?php if (!$rules): ?>
                    <tr><td colspan="6">Aucune regle.</td></tr>
                <?php endif; ?>
                <?php foreach ($rules as $rule): ?>
                    <tr>
                        <td><?php echo mdj_html((string) $rule['label']); ?></td>
                        <td><?php echo mdj_html((string) $rule['field']); ?></td>
                        <td><?php echo mdj_html((string) $rule['match_type']); ?></td>
                        <td><code><?php echo mdj_html((string) $rule['pattern']); ?></code></td>
                        <td><?php echo mdj_html((string) $rule['action']); ?></td>
                        <td><?php mdj_admin_action_button('delete_rule', (int) $rule['id'], 'Supprimer'); ?></td>
                    </tr>
                <?php endforeach; ?>
            </tbody>
        </table>

        <h3>Ajouter une regle</h3>
        <form method="post" class="rule-form">
            <input type="hidden" name="csrf" value="<?php echo mdj_html($_SESSION['mdj_csrf']); ?>">
            <input type="hidden" name="action" value="add_rule">
            <label>Libelle <input name="label"></label>
            <label>
                Champ
                <select name="field">
                    <option value="content">Commentaire</option>
                    <option value="author_name">Nom</option>
                    <option value="author_email">E-mail</option>
                    <option value="author_url">Site web</option>
                    <option value="user_ip">IP</option>
                </select>
            </label>
            <label>
                Type
                <select name="match_type">
                    <option value="contains">Contient</option>
                    <option value="regex">Expression reguliere</option>
                    <option value="email_domain">Domaine e-mail</option>
                    <option value="equals">Egal a</option>
                </select>
            </label>
            <label>Motif <input name="pattern" required></label>
            <label>
                Action
                <select name="rule_action">
                    <option value="reject">Rejeter</option>
                    <option value="hold">Garder en attente</option>
                    <option value="approve">Valider</option>
                </select>
            </label>
            <button type="submit">Ajouter la regle</button>
        </form>
    </section>
</body>
</html>
