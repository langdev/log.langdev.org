<?php
class Log
{
	var $date; // YYMMDD format
	var $threshold = 900; // seconds

	function Log($date) {
		$this->date = $date;
	}

	function path() {
		if ($this->is_today())
			return "logs/langdev.log";
		else
			return "logs/langdev.log.$this->date";
	}

	function available() {
		return file_exists($this->path());
	}

	/*static*/ function today() {
		return new Log(date('Ymd'));
	}

	function is_today() {
		return $this->date == date('Ymd');
	}

	function title() {
		$y = substr($this->date, 0, 4);
		$m = substr($this->date, 4, 2);
		$d = substr($this->date, 6, 2);
		return "$y-$m-$d";
	}

	function messages() {
		$messages = array();
		$fp = fopen($this->path(), 'r');
		$no = 1;
		while ($line = fgets($fp)) {
			if (preg_match('/PRIVMSG/', $line)) {
				preg_match('/^.*? \[(.+?) .*?\] .*? (<<<|>>>) (?::(.+?)!.+? )?PRIVMSG #.+? :(.+)$/', $line, $parts);
				$messages[] = array(
					'no' => $no,
					'time' => strtotime($parts[1]),
					'nick' => $parts[3],
					'text' => $parts[4],
					'bot?' => !$parts[3],
				);
				$no++;
			}
		}
		fclose($fp);
		return $messages;
	}

	function grouped_messages() {
		$messages = $this->messages();
		$groups = array();
		$group = array();
		$prev_time = $messages[0]['time'];
		foreach ($messages as $msg) {
			if (($msg['time'] - $prev_time) > $this->threshold) {
				// 그룹이 갈린다. 이 메시지 앞까지 한 그룹이 된다.
				$groups[] = $group;
				$group = array();
			}
			$group[] = $msg;
			$prev_time = $msg['time'];
		}
		if (!empty($group))
			$groups['ungrouped'] = $group;
		return $groups;
	}

	function uri() {
		return "/bot/log/" . $this->title();
	}
}

function autolink($string) {
	return preg_replace("#([a-z]+)://[-0-9a-z_.@:~\\#%=+?/$;,&]+#i", '<a href="$0">$0</a>', $string);
}

/////////////////////////////

$path = trim(@$_SERVER['PATH_INFO'], '/');
if (empty($path)) {
	$log = Log::today();
	header("Location: " . $log->uri());
	exit;
}

if ($path != 'atom'):
	$log = new Log(preg_replace('/^(\d{4})-(\d{2})-(\d{2})$/', '$1$2$3', $path));
	if (!$log->available()) {
		header("HTTP/1.1 404 Not Found");
		echo "Not found";
		exit;
	}
?>
<!DOCTYPE html>
<html>
<head>
	<title>#langdev log: <?=$log->date?></title>
	<link rel="stylesheet" href="/bot/style.css" type="text/css">
	<style type="text/css">
	#nav { font-size: 0.6em; margin-left: 2em; color: #999; vertical-align: middle; }
	#nav a { color: #999; text-decoration: underline; }
	#nav a:hover { background-color: transparent; }
	table { border-collapse: collapse; margin-bottom: 2em; border-top: 2px solid #999; }
	td { padding: 0.5em 1em; border-top: 1px solid #ddd; line-height: 1.4; }
	.time { font-size: 0.85em; color: #999; }
	.time a { color: #999; text-decoration: none; }
	.time a:hover { background-color: #ccc; color: #fff; }
	.nickname { font-size: 0.9em; }
	.link { border: 1px solid #ddd; background-color: #f8f8f8; padding: 0.5em; margin-bottom: 2em; }
	.new { font-size: xx-small; vertical-align: super; color: #000; }
	</style>
</head>
<body>
<h1>Log of #langdev</h1>

<h2><?=$log->title()?>
<span id="nav">
	<a href="/bot/log/<?=date('Y-m-d', strtotime('yesterday'))?>">어제</a> 또는 <a href="/bot/log/">오늘</a>로 날아가기 / <a href="/bot/log/atom">Atom 피드</a><span class="new">new!</span>
</span></h2>

<?php foreach ($log->grouped_messages() as $group): ?>
<table>
	<?php foreach ($group as $msg): ?>
	<tr id="line<?=$msg['no']?>">
		<td class="time" title="<?=date('c', $msg['time'])?>"><a href="#line<?=$msg['no']?>"><?=date('H:i:s', $msg['time'])?></a></td>
		<td class="nickname"><?=!$msg['bot?'] ? htmlspecialchars($msg['nick']) : '<strong>낚지</strong>'?></td>
		<td class="message"><?=autolink(htmlspecialchars($msg['text']))?></td>
	</tr>
	<?php endforeach; ?>
</table>
<?php endforeach; ?>

<p><a href="/bot/">낚지</a>가 기록합니다.</a></p>
</body>
</html>
<?php
else:
	header("Content-Type: application/atom+xml");
	echo '<?xml version="1.0" encoding="utf-8"?>';
	$log = Log::today();
	$data = $log->grouped_messages();
	unset($data['ungrouped']);
	function _last($array) {
		return $array[count($array) - 1];
	}
	$last_msg = _last(_last($data));
	$no = 1;
?>
<feed xmlns="http://www.w3.org/2005/Atom">
	<title>Log of #langdev</title>
	<link href="http://ditto.just4fun.co.kr/bot/log" />
	<updated><?=date('c', $last_msg['time'])?></updated>
<?php foreach ($data as $group): ?>
	<entry>
		<title><?=$log->title()?>#<?=$no?></title>
		<link href="http://ditto.just4fun.co.kr<?=$log->uri()?>#line<?=$group[0]['no']?>" />
		<updated><?php $last_msg = _last($group); echo date('c', $last_msg['time']); ?></updated>
		<content type="xhtml">
			<table xmlns="http://www.w3.org/1999/xhtml">
				<?php foreach ($group as $msg): ?>
				<tr id="line<?=$msg['no']?>">
					<td class="time" title="<?=date('c', $msg['time'])?>"><a href="#line<?=$msg['no']?>"><?=date('H:i:s', $msg['time'])?></a></td>
					<td class="nickname"><?=!$msg['bot?'] ? htmlspecialchars($msg['nick']) : '<strong>낚지</strong>'?></td>
					<td class="message"><?=autolink(htmlspecialchars($msg['text']))?></td>
				</tr>
				<?php endforeach; ?>
			</table>
		</content>
	</entry>
<?php $no++; endforeach; ?>
</feed>
<?php
endif;
