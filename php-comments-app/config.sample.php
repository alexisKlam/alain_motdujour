<?php

return [
    'db' => [
        'dsn' => 'mysql:host=localhost;dbname=YOUR_DATABASE;charset=utf8mb4',
        'user' => 'YOUR_DATABASE_USER',
        'password' => 'YOUR_DATABASE_PASSWORD',
    ],
    'admin' => [
        // Generate with: php -r "echo password_hash('your-password', PASSWORD_DEFAULT), PHP_EOL;"
        'password_hash' => '$2y$10$replace-this-hash-before-deploying',
    ],
    'allowed_origins' => [
        'https://lemotdujour.fr',
    ],
    'auto_approve' => false,
    'success_message' => 'Merci. Votre commentaire est en attente de validation.',
    'setup_key' => 'change-this-random-install-key',
];
