<?php
ini_set('display_errors', 'Off');
require 'auth.php';

class Log
{
	var $date; // YYMMDD format

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

	/*static*/ function random() {
		$rand = rand(30, 600);
		return new Log(date('Ymd', strtotime("$rand days ago")));
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

	function messages($from = 0) {
		$messages = array();
		$fp = @fopen($this->path(), 'r');
		if (!$fp)
			return $messages;
		$no = 0;
		while ($line = fgets($fp)) {
			if (preg_match('/PRIVMSG/', $line)) {
				$no++;
				if ($no < $from) continue;
				if (!preg_match('/^.*?\[(.+?)(?: #.*?)?\].*? (<<<|>>>) (?::(.+?)!.+? )?PRIVMSG #.+? :(.+)$/', $line, $parts))
					continue;
				$is_bot = !$parts[3];

				if ($is_bot && preg_match('/^<(.+?)> (.*)$/', $parts[4], $tmp)) {
					$parts[3] = $tmp[1];
					$parts[4] = $tmp[2];
					$is_bot = false;
				}

				$messages[] = array(
					'no' => $no,
					'time' => strtotime($parts[1]),
					'nick' => $parts[3],
					'text' => $parts[4],
					'bot?' => $is_bot,
				);
			}
		}
		fclose($fp);
		return $messages;
	}

	function uri() {
		return "/log/" . $this->title();
	}
}

define('GROUP_THRES', 900 /*seconds*/);

function group_messages($messages) {
	$groups = array();
	$group = array();
	$prev_time = $messages[0]['time'];
	foreach ($messages as $msg) {
		if (($msg['time'] - $prev_time) > GROUP_THRES) {
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

class Synonym
{
	var $dict;

	function Synonym() {
		$dict = array();
		$fp = fopen("synonyms", 'r');
		while ($line = fgets($fp)) {
			$line = trim($line);
			$words = explode(' ', $line);
			foreach ($words as $word) {
				$dict[$word] = $words;
			}
		}
		$this->dict = $dict;
	}

	function get($word) {
		$word = strtolower($word);
		$words = $this->dict[$word];
		if (!isset($words)) $words = array($word);
		return $words;
	}
}

class SearchQuery
{
	var $keyword;
	var $words;
	var $days = 7;
	var $offset = 0;

	function SearchQuery($keyword) {
		$synonym = new Synonym();
		$this->keyword = $keyword;
		$this->words = $synonym->get($this->keyword);
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
			foreach ($this->words as $word) {
				if (stripos($msg['text'], $word) !== FALSE) {
					$result[] = $msg;
					break;
				}
			}
		}
		return $result;
	}
}

function autolink($string) {
	return preg_replace("#(https?)://([-0-9a-z_.@:~\\#%=+?!/$;,&]+)#i", '<a href="http://fw.mearie.org/$2" rel="noreferrer">$0</a>', $string);
}

function h($string) { return htmlspecialchars($string); }

function print_lines($log, $lines) {
	foreach ($lines as $msg): ?>
				<tr id="line<?=$msg['no']?>">
					<td class="time" title="<?=date('c', $msg['time'])?>"><a href="<?=$log->uri()?>#line<?=$msg['no']?>"><?=date('H:i:s', $msg['time'])?></a></td>
					<td class="nickname"><i>&lt;</i><?=!$msg['bot?'] ? h($msg['nick']) : '<strong>낚지</strong>'?><i>&gt;</i></td>
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
	<meta charset="UTF-8" />
	<title>#langdev log: <?=$title?></title>
	<meta name="viewport" content="width=device-width" />
	<link rel="stylesheet" href="/style.css" type="text/css">
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
	.nickname { font-size: 0.9em; text-align: right; }
	.link { border: 1px solid #ddd; background-color: #f8f8f8; padding: 0.5em; margin-bottom: 2em; }
	.new { font-size: xx-small; vertical-align: super; color: #000; }
	.highlight { background-color: #ff0; }
	#update a { font-size: 1.2em; text-align: center; border: 1px solid #ccc; background-color: #f4f4f4; display: block; padding: 0.5em; }
	i { font-size: 0; color: transparent; }
	
	@media only screen and (max-device-width: 480px) {
		body { margin: 0; }
		h2 { text-align: center; }
		#nav { display: block; margin-left: 0; font-size: 0.8em; }
		.time { display: none; }
	}
	</style>
	<script type="text/javascript" src="http://ajax.googleapis.com/ajax/libs/jquery/1.4/jquery.min.js"></script>
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

if ($path == 'random') {
	$log = Log::random();
	header("Location: " . $log->uri());
	exit;
} else if ($path == 'atom'):
	header("Content-Type: application/atom+xml");
	echo '<?xml version="1.0" encoding="utf-8"?>';
	$log = Log::today();
	$data = array_reverse(group_messages($log->messages()));
	unset($data['ungrouped']);
	$no = count($data);
?>
<feed xmlns="http://www.w3.org/2005/Atom">
	<title>Log of #langdev</title>
	<link href="http://log.langdev.org/" />
	<updated><?=date('c', $data[0][count($data[0])-1]['time'])?></updated>
<?php foreach ($data as $group): ?>
	<entry>
		<title><?=$log->title()?>#<?=$no?></title>
		<link href="http://log.langdev.org<?=$log->uri()?>#line<?=$group[0]['no']?>" />
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
<?php print_header("search" . ($query ? ": $query->keyword" : '')); ?>
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
var re = /<?=h(implode('|', array_map('preg_quote', $query->words)))?>/gi
var repl = "<span class=\"highlight\">$&</span>"
var cells = document.getElementsByTagName('td')
for (var i = 0; i < cells.length; i++) {
	var cell = cells[i]
	if (cell.className == 'message' && cell.innerHTML.match(re))
	{
		var content = []
		for (var j = 0; j < cell.childNodes.length; j++)
		{
			var node = cell.childNodes[j]
			if (node.nodeType == 3)
				content.push(node.nodeValue.replace(re, repl))
			else if (node.nodeType == 1 && node.tagName == 'A') {
				content.push('<a href="' + node.href + '">')
				content.push(node.innerHTML.replace(re, repl))
				content.push('</a>')
			}
		}
		cell.innerHTML = content.join('')
	}
}
</script>
<?php endif; ?>
</body>
</html>

<?php
elseif ($path == 'say'):
	$ctx = stream_context_create(array(
		'http' => array(
			'method' => 'POST',
			'content' => "nick=$_SERVER[PHP_AUTH_USER]&msg=" . rawurlencode($_POST['msg']),
		)
	));
	file_get_contents("http://localhost:6667/", false, $ctx);
else:
	$log = new Log(preg_replace('/^(\d{4})-(\d{2})-(\d{2})$/', '$1$2$3', $path));
	if (!$log->available()) {
		header("HTTP/1.1 404 Not Found");
		echo "Not found";
		exit;
	}
	if (empty($_GET['from'])):
		$messages = $log->messages();
		$count = count($messages);
		$lines = $messages[$count-1]['no'];
		if ($only_recent = $log->is_today() && !isset($_GET['full'])) {
			$now = time();
			$from = 0;
			foreach ($messages as $i => $msg) {
				if (($now - $msg['time']) <= 60*30) {
					$from = $i;
					break;
				}
			}
			if ($count - $from < 50)
				$from = $count - 50;
			if ($from == 0)
				$only_recent = false;
			else
				$messages = array_slice($messages, $from);
		}
?>
<?php print_header($log->title()); ?>
<h1>Log of #langdev</h1>

<form method="get" action="search" id="tagline">
<p><input type="text" name="q" value="<?=h(@$query->keyword)?>" /> <input type="submit" value="찾기" /> / <a href="/log/atom">Atom 피드</a></p>
</form>

<h2><?=$log->title()?>
<span id="nav">
	<a href="/log/<?=date('Y-m-d', strtotime('yesterday'))?>">어제</a> 또는 <a href="/log/">오늘</a>로 날아가기 / <a href="/log/random">운 좋은 예감</a> / <a href="#updates">맨 아래로 &darr;</a>
</span></h2>

<?php if ($only_recent): ?>
<p>최근 대화만 표시하고 있습니다. <a href="?full">전체 보기</a></p>
<?php endif; ?>

<?php foreach (group_messages($messages) as $group): ?>
<table>
	<?php print_lines($log, $group); ?>
</table>
<?php endforeach; ?>

<?php if ($log->is_today()): ?>
<table id="updates"></table>

<form method="post" action="say" id="say">
<p>&lt;<?=htmlspecialchars($_SERVER['PHP_AUTH_USER'])?>&gt; <input type="text" name="msg" id="msg" size="50" /> <input type="submit" value="Say!" /> 갱신 주기: <span id="period">3000</span>ms</p>
</form>

<script type="text/javascript">
var from = <?=$lines + 1?>;
var interval = 3000;
var seq = 0;
function _update_log() {
	var _from = from;
	$.get('?from=' + _from, function (data) {
		if (from > _from) return;
		var willScroll = $(document).height() <= $(window).scrollTop()+$(window).height() + 20;
		$('#updates').append(data)
		if (willScroll)
			$(window).scrollTop($(document).height() + 100000)
		$('#period').text(interval)
	})
}
function update_log() {
	_update_log()
	window.setTimeout(update_log, interval)
}
window.setTimeout(update_log, interval)

$('#say').submit(function(event) {
	$.post($(this).attr('action'), $(this).serialize(), function() {
		_update_log()
	})
	$('#msg').attr('value', '')
	event.preventDefault()
})
</script>
<?php endif; ?>

<p>낚지가 기록합니다.</a></p>
</body>
</html>
<?php
	else:
		$messages = $log->messages((int)$_GET['from']);
		if (!empty($messages)) {
			$lines = $messages[count($messages)-1]['no'] + 1;
			print_lines($log, $messages);
			$js = "from=$lines;interval=3000;";
		} else $js = "interval=Math.min(10000, interval+100)";
		echo "<script type='text/javascript'>$js</script>";
	endif;
endif;
