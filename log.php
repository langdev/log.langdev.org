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

	function yesterday() {
		return $this->days_before(1);
	}

	function days_before($days) {
		list($y, $m, $d) = $this->parsed_date();
		$timestamp = mktime(0, 0, 0, $m, $d, $y);
		$yesterday = strtotime("-$days day", $timestamp);
		return new Log(date('Ymd', $yesterday));
	}

	function parsed_date() {
		$y = substr($this->date, 0, 4);
		$m = substr($this->date, 4, 2);
		$d = substr($this->date, 6, 2);
		return array($y, $m, $d);
	}

	function title() {
		list($y, $m, $d) = $this->parsed_date();
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

class SearchQuery
{
	var $keyword;
	var $days = 7;
	var $offset = 0;

	function SearchQuery($keyword) {
		$this->keyword = $keyword;
	}

	function perform() {
		$log = Log::today();
		if ($this->offset > 0)
			$log = $log->days_before($this->offset * $this->days);

		$results = array();
		for ($days = 0; $days < $this->days; $days++) {
			$result = $this->filter($log->messages());
			if (!empty($result))
				// descending order
				$results[$log->date] = array_reverse($result);
			$log = $log->yesterday();
		}
		return $results;
	}

	function filter($messages) {
		$result = array();
		foreach ($messages as $msg) {
			if (stripos($msg['text'], $this->keyword) !== FALSE)
				$result[] = $msg;
		}
		return $result;
	}
}

function autolink($string) {
	return preg_replace("#([a-z]+)://[-0-9a-z_.@:~\\#%=+?/$;,&]+#i", '<a href="$0">$0</a>', $string);
}

function h($string) { return htmlspecialchars($string); }

function print_lines($log, $lines) {
	foreach ($lines as $msg): ?>
				<tr id="line<?=$msg['no']?>">
					<td class="time" title="<?=date('c', $msg['time'])?>"><a href="<?=$log->uri()?>#line<?=$msg['no']?>"><?=date('H:i:s', $msg['time'])?></a></td>
					<td class="nickname"><?=!$msg['bot?'] ? h($msg['nick']) : '<strong>낚지</strong>'?></td>
					<td class="message"><?=autolink(h($msg['text']))?></td>
				</tr>
	<?php
	endforeach;
}

function print_header($title) {
?>
<!DOCTYPE html>
<html>
<head>
	<title>#langdev log: <?=$title?></title>
	<link rel="stylesheet" href="/bot/style.css" type="text/css">
	<style type="text/css">
	#nav { font-size: 0.6em; margin-left: 2em; color: #999; vertical-align: middle; }
	#nav a { color: #999; text-decoration: underline; }
	#nav a:hover { background-color: transparent; }
	form { border: 1px solid #ccc; padding: 1em; clear: both; }
	form#tagline { clear: right; border: none; padding: 0; }
	form p { margin: 0; text-indent: 0; }
	table { border-collapse: collapse; margin-bottom: 2em; border-top: 2px solid #999; }
	td { padding: 0.5em 1em; border-top: 1px solid #ddd; line-height: 1.4; }
	.time { font-size: 0.85em; color: #999; }
	.time a { color: #999; text-decoration: none; }
	.time a:hover { background-color: #ccc; color: #fff; }
	.nickname { font-size: 0.9em; }
	.link { border: 1px solid #ddd; background-color: #f8f8f8; padding: 0.5em; margin-bottom: 2em; }
	.new { font-size: xx-small; vertical-align: super; color: #000; }
	.highlight { background-color: #ff0; }
	</style>
</head>
<body>
<?php
}

/////////////////////////////

$path = trim(@$_SERVER['PATH_INFO'], '/');
if (empty($path)) {
	$log = Log::today();
	header("Location: " . $log->uri());
	exit;
}

if ($path == 'atom'):
	header("Content-Type: application/atom+xml");
	echo '<?xml version="1.0" encoding="utf-8"?>';
	$log = Log::today();
	$data = array_reverse($log->grouped_messages());
	unset($data['ungrouped']);
	$no = count($data);
?>
<feed xmlns="http://www.w3.org/2005/Atom">
	<title>Log of #langdev</title>
	<link href="http://ditto.just4fun.co.kr/bot/log" />
	<updated><?=date('c', $data[0][count($data[0])-1]['time'])?></updated>
<?php foreach ($data as $group): ?>
	<entry>
		<title><?=$log->title()?>#<?=$no?></title>
		<link href="http://ditto.just4fun.co.kr<?=$log->uri()?>#line<?=$group[0]['no']?>" />
		<updated><?php echo date('c', $group[count($group)-1]['time']); ?></updated>
		<content type="xhtml">
			<table xmlns="http://www.w3.org/1999/xhtml">
				<?php print_lines($log, $group); ?>
			</table>
		</content>
	</entry>
<?php $no--; endforeach; ?>
</feed>
<?php
elseif ($path == 'search'):
	if (isset($_GET['q'])) {
		$query = new SearchQuery(trim($_GET['q']));
		$query->offset = !empty($_GET['offset']) ? (int)$_GET['offset'] : 0;
		$result = $query->perform();
	} else
		$query = null;
?>
<?php print_header("search"); ?>
<h1>Log Search</h1>

<form method="get" action="">
	<p>최근 7일 간의 기록을 검색합니다.</p>
	<p>검색어: <input type="text" name="q" value="<?=h($query->keyword)?>" /> <input type="submit" value="찾기" /></p>
</form>

<?php if ($query): ?>
<?php if (!empty($result)): ?>
<?php foreach ($result as $date => $messages): $log = new Log($date); ?>
<div class="day">
	<h2><a href="<?=$log->uri()?>"><?=$log->title()?></a></h2>
	<table>
		<?php print_lines($log, $messages); ?>
	</table>
</div>
<?php endforeach; ?>
<?php else: ?>
<p>검색 결과가 없습니다.</p>
<?php endif; ?>

<p><a href="?q=<?=urlencode(h($query->keyword))?>&amp;offset=<?=$query->offset + 1?>">이전 7일 &rarr;</a></p>

<script type="text/javascript">
var re = /<?=h(preg_quote($query->keyword))?>/gi
var cells = document.getElementsByTagName('td')
for (var i = 0; i < cells.length; i++) {
	var cell = cells[i]
	if (cell.className == 'message')
		cell.innerHTML = cell.innerHTML.replace(re, "<span class=\"highlight\">$&</span>");
}
</script>
<?php endif; ?>
</body>
</html>

<?php
else:
	$log = new Log(preg_replace('/^(\d{4})-(\d{2})-(\d{2})$/', '$1$2$3', $path));
	if (!$log->available()) {
		header("HTTP/1.1 404 Not Found");
		echo "Not found";
		exit;
	}
?>
<?php print_header($log->title()); ?>
<h1>Log of #langdev</h1>

<form method="get" action="search" id="tagline">
<p><input type="text" name="q" value="<?=h($query->keyword)?>" /> <input type="submit" value="찾기" /></p>
</form>

<h2><?=$log->title()?>
<span id="nav">
	<a href="/bot/log/<?=date('Y-m-d', strtotime('yesterday'))?>">어제</a> 또는 <a href="/bot/log/">오늘</a>로 날아가기 / <a href="/bot/log/atom">Atom 피드</a>
</span></h2>

<?php foreach ($log->grouped_messages() as $group): ?>
<table>
	<?php print_lines($log, $group); ?>
</table>
<?php endforeach; ?>

<p><a href="/bot/">낚지</a>가 기록합니다.</a></p>
</body>
</html>
<?php
endif;
