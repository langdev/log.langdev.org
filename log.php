<?php
$today = date('Y-m-d');
if (!isset($_SERVER['PATH_INFO']) || !preg_match('/^\/[0-9]{4}-[0-9]{2}-[0-9]{2}$/', $_SERVER['PATH_INFO'])) {
	$file = 'langdev.log';
	$date = $today;
} else {
	$date = substr($_SERVER['PATH_INFO'], 1);
	if ($date != $today)
		$file = 'langdev.log.' . str_replace('-', '', $date);
	else
		$file = 'langdev.log';
}
$file = 'logs/'.$file;
$collect_links = @$_SERVER['QUERY_STRING'] == 'links';
?>
<!DOCTYPE html>
<html>
<head>
	<title>#langdev log: <?=$date?></title>
	<link rel="stylesheet" href="/bot/style.css" type="text/css">
	<style type="text/css">
	#nav { font-size: 0.6em; margin-left: 2em; color: #999; vertical-align: middle; }
	#nav a { color: #999; text-decoration: underline; }
	#nav a:hover { background-color: transparent; }
	table { border-collapse: collapse; }
	td { padding: 0.5em 1em; border-top: 1px solid #ddd; line-height: 1.4; }
	.time { font-size: 0.85em; color: #999; }
	.time a { color: #999; text-decoration: none; }
	.time a:hover { background-color: #ccc; color: #fff; }
	.nickname { font-size: 0.9em; }
	.link { border: 1px solid #ddd; background-color: #f8f8f8; padding: 0.5em; margin-bottom: 2em; }
	</style>
</head>
<body>
<h1>Log of #langdev</h1>

<h2><?=$date?>
<span id="nav">
	<a href="/bot/log/<?=date('Y-m-d', strtotime('yesterday'))?>">어제</a> 또는 <a href="/bot/log/">오늘</a>로 날아가기 /
	<?php if ($collect_links): ?><a href="/bot/log/<?=$date?>">전체 보기</a>
	<?php else: ?><a href="?links">링크만 모아보기</a><?php endif; ?>
</span></h2>

<?php
function autolink($string) {
	return preg_replace("#([a-z]+)://[-0-9a-z_.@:~\\#%=+?/$;,&]+#i", '<a href="$0">$0</a>', $string);
}

function grep_messages($part) {
	preg_match_all('/^.*? \[(.+?) .*?\] .*? <<< :(.+?)!.+? PRIVMSG #.+? :(.+)$/m', $part, $messages, PREG_SET_ORDER);
	return $messages;
}

if ($collect_links):
$parts = explode("\n--", `grep "<<< .* PRIVMSG" $file | grep -C 1 "http:"`);
foreach (array_reverse($parts) as $part) {
	preg_match_all('/^.*? \[(.+?) .*?\] .*? <<< :(.+?)!.+? PRIVMSG #.+? :(.+)$/m', $part, $messages, PREG_SET_ORDER);
?>
<table class="link">
<?php
	foreach ($messages as $line) {
		list(, $time, $nick, $message) = $line;
?>
<tr>
	<td class="time"><?=date('H:i:s', strtotime($time))?></td>
	<td class="nickname"><?=htmlspecialchars($nick)?></td>
	<td class="message"><?=autolink(htmlspecialchars($message))?></td>
</tr>
<?php
	}
?>
</table>
<?php
}
else:
$part = `grep "<<< .* PRIVMSG" $file`;
$messages = grep_messages($part);
?>
<table>
<?php
	$no = 1;
	foreach ($messages as $line) {
		list(, $time, $nick, $message) = $line;
		$no++;
?>
<tr id="line<?=$no?>">
	<td class="time" title="<?=$time?>"><a href="#line<?=$no?>"><?=date('H:i:s', strtotime($time))?></a></td>
	<td class="nickname"><?=htmlspecialchars($nick)?></td>
	<td class="message"><?=autolink(htmlspecialchars($message))?></td>
</tr>
<?php
	}
?>
</table>
<?php endif; ?>

<p><a href="/bot/">낚지</a>가 기록합니다.</a></p>
</body>
</html>
