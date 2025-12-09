<?php
// === DB 설정 ===
$host = 'localhost';
$dbname = ''; // 본인의 DB 이름
$username = '';   // 본인의 DB 아이디
$password = ''; // 본인의 DB 비번

try {
    $pdo = new PDO("mysql:host=$host;dbname=$dbname;charset=utf8", $username, $password);
    $pdo->setAttribute(PDO::ATTR_ERRMODE, PDO::ERRMODE_EXCEPTION);
} catch(PDOException $e) {
    die("DB 연결 실패: " . $e->getMessage());
}

// === RSS 추가 로직 ===
if ($_SERVER['REQUEST_METHOD'] === 'POST' && !empty($_POST['rss_url'])) {
    $stmt = $pdo->prepare("INSERT IGNORE INTO rss_feeds (url) VALUES (:url)");
    $stmt->execute([':url' => $_POST['rss_url']]);
    header("Location: " . $_SERVER['PHP_SELF']); // 새로고침
    exit;
}

// === RSS 삭제 로직 ===
if (isset($_GET['delete'])) {
    $stmt = $pdo->prepare("DELETE FROM rss_feeds WHERE id = :id");
    $stmt->execute([':id' => $_GET['delete']]);
    header("Location: " . $_SERVER['PHP_SELF']);
    exit;
}

// === 목록 조회 ===
$stmt = $pdo->query("SELECT * FROM rss_feeds ORDER BY id DESC");
$feeds = $stmt->fetchAll(PDO::FETCH_ASSOC);
?>

<!DOCTYPE html>
<html lang="ko">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>뉴스 봇 관리자 (PHP)</title>
    <style>
        body { font-family: sans-serif; max-width: 600px; margin: 2rem auto; padding: 0 1rem; }
        input[type="text"] { width: 70%; padding: 10px; }
        button { padding: 10px 20px; background: #007bff; color: white; border: none; cursor: pointer; }
        ul { list-style: none; padding: 0; }
        li { background: #f4f4f4; margin: 5px 0; padding: 10px; display: flex; justify-content: space-between; align-items: center; }
        .delete-btn { color: red; text-decoration: none; font-weight: bold; }
    </style>
</head>
<body>
    <h1>📰 RSS 피드 관리</h1>

    <form method="POST">
        <input type="text" name="rss_url" placeholder="https://example.com/rss" required>
        <button type="submit">추가</button>
    </form>

    <h3>등록된 목록 (<?= count($feeds) ?>개)</h3>
    <ul>
        <?php foreach ($feeds as $feed): ?>
            <li>
                <span><?= htmlspecialchars($feed['url']) ?></span>
                <a href="?delete=<?= $feed['id'] ?>" class="delete-btn">[삭제]</a>
            </li>
        <?php endforeach; ?>
    </ul>
</body>
</html>
