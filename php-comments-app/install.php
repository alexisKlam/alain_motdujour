<?php

declare(strict_types=1);

require __DIR__ . '/lib.php';

$config = mdj_config();
$setup_key = (string) ($config['setup_key'] ?? '');
$provided_key = (string) ($_GET['key'] ?? $_POST['key'] ?? '');
$allowed = $setup_key !== '' && hash_equals($setup_key, $provided_key);
$messages = [];

if ($allowed && $_SERVER['REQUEST_METHOD'] === 'POST' && isset($_POST['install'])) {
    foreach (mdj_schema_sql() as $sql) {
        mdj_pdo()->exec($sql);
    }
    $messages[] = 'Tables MySQL creees ou deja presentes.';
}

if ($allowed && $_SERVER['REQUEST_METHOD'] === 'POST' && isset($_POST['password_to_hash'])) {
    $password = (string) $_POST['password_to_hash'];
    if ($password !== '') {
        $messages[] = 'Hash admin: ' . password_hash($password, PASSWORD_DEFAULT);
    }
}
?>
<!doctype html>
<html lang="fr">
<head>
    <meta charset="utf-8">
    <meta name="viewport" content="width=device-width, initial-scale=1">
    <title>Installation commentaires MDJ</title>
    <style>
        body { font-family: system-ui, sans-serif; max-width: 760px; margin: 40px auto; padding: 0 18px; color: #333; }
        label { display: grid; gap: 6px; margin: 14px 0; }
        input { padding: 8px 10px; font: inherit; }
        button { padding: 8px 14px; font: inherit; }
        code, pre { background: #f4f4f4; padding: 2px 4px; }
        .message { padding: 10px 12px; background: #eef8ef; border-left: 4px solid #2f6f3e; }
    </style>
</head>
<body>
    <h1>Installation commentaires MDJ</h1>

    <?php foreach ($messages as $message): ?>
        <p class="message"><?php echo mdj_html($message); ?></p>
    <?php endforeach; ?>

    <?php if (!$allowed): ?>
        <p>Renseigner la cle <code>setup_key</code> definie dans <code>config.php</code>.</p>
        <form method="get">
            <label>
                Cle d'installation
                <input name="key" type="password" required>
            </label>
            <button type="submit">Continuer</button>
        </form>
    <?php else: ?>
        <h2>1. Creer les tables</h2>
        <form method="post">
            <input type="hidden" name="key" value="<?php echo mdj_html($provided_key); ?>">
            <button name="install" value="1" type="submit">Creer ou mettre a jour les tables</button>
        </form>

        <h2>2. Generer un hash de mot de passe admin</h2>
        <form method="post">
            <input type="hidden" name="key" value="<?php echo mdj_html($provided_key); ?>">
            <label>
                Mot de passe admin
                <input name="password_to_hash" type="password" autocomplete="new-password">
            </label>
            <button type="submit">Generer le hash</button>
        </form>

        <p>Copier le hash genere dans <code>config.php</code>, puis supprimer <code>install.php</code> du serveur.</p>
    <?php endif; ?>
</body>
</html>
