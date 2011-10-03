<?php
ini_set('display_errors', 'Off');
require 'auth.php';
require 'sphinx/sphinxapi-2.0.1-beta.php';

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
			if (!preg_match('/^.*?\[(.+?)(?: #.*?)?\].*? (<<<|>>>) (.+)$/', $line, $parts))
				continue;

			list(, $timestamp, $direction, $data) = $parts;
			
			if (preg_match('/PRIVMSG/', $data)) {
				$no++;
				if ($no < $from) continue;
				if (!preg_match('/^(?::(.+?)!.+? )?PRIVMSG #.+? :(.+)$/', $data, $parts))
					continue;
				$is_bot = !$parts[1];

				if ($is_bot && preg_match('/^<(.+?)> (.*)$/', $parts[2], $tmp)) {
					$parts[1] = $tmp[1];
					$parts[2] = $tmp[2];
					$is_bot = false;
				}

				$messages[] = array(
				    'type' => 'privmsg',
					'no' => $no,
					'time' => strtotime($timestamp),
					'nick' => $parts[1],
					'text' => $parts[2],
					'bot?' => $is_bot,
				);
			} else if ($direction == '>>>' && !$from &&
			        preg_match('/^JOIN #langdev/', $data)) {
				$messages[] = array(
				    'type' => 'join',
				    'time' => strtotime($timestamp),
				    'bot?' => true,
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
	var $days = 14;
	var $offset = 0;

	function SearchQuery($keyword) {
		$synonym = new Synonym();
		$this->keyword = $keyword;
		$this->words = $synonym->get($keyword);
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

class SphinxSearchQuery
{
	var $keyword;
	var $offset;
	var $message;
	var $total;
	var $COUNT_PER_PAGE;

	function SphinxSearchQuery($keyword) {
		$synonym = new Synonym();
		$this->keyword = $keyword;
		$this->words = $synonym->get($keyword);
		$this->offset = 0;
		$this->message = "";
		$this->COUNT_PER_PAGE = 100;
	}

	function perform() {
		$results = array();

		if (strlen(trim($this->keyword)) == 0)
			return $results;

		// initialize sphinxsearch client
		$sortby = "@id DESC";   // docid format=("yyyymmdd%08d", lineno)
		//$sortexpr = "";
		$ranker = SPH_RANK_PROXIMITY_BM25;
		$index = "*";

		$client = new SphinxClient();
		$client->SetServer("localhost", 9312);
		$client->SetConnectTimeout(1);
		$client->SetArrayResult(true);
		$client->SetWeights(array(100, 1));

		$client->SetSortMode(SPH_SORT_EXTENDED, $sortby);
		//$client->SetSortMode(SPH_SORT_EXPR, $sortexpr);
		$client->SetLimits($this->offset * $this->COUNT_PER_PAGE, $this->COUNT_PER_PAGE, 100000);
		$client->SetRankingMode($ranker);

		// do query!!
		if (count($this->words) == 1) {
			$client->SetMatchMode(SPH_MATCH_ALL);
			$res = $client->Query($this->keyword, $index);
		} else {
			$client->SetMatchMode(SPH_MATCH_BOOLEAN);
			$res = $client->Query(implode(' | ', $this->words), $index);
		}

		if ($res == false) {
			$err = $client->GetLastError();
			$this->message = "Query Failed: $err";
		}
		else {
			if (array_key_exists("matches", $res) and is_array($res["matches"])) {
				$this->total = $res["total"];
				$this->message = "총 $res[total]개의 로그가 검색되었습니다.";
				foreach ($res["matches"] as $docinfo) {
					$msg = array(
						'no' => $docinfo['attrs']['no'],
						'type' => 'privmsg',
						'time' => $docinfo['attrs']['time'],
						'nick' => $docinfo['attrs']['nick'],
						'text' => $docinfo['attrs']['content'],
						'bot?' => $docinfo['attrs']['bot'],
					);

					$index = date('Ymd', $msg['time']);
					if (array_key_exists($index, $results))
						$results[$index][] = $msg;
					else
						$results[$index] = array($msg);
				}
			}
			else {
				$this->message = "No more logs...";
			}
		}

		return $results;
	}

	function paging() {
		$result = "Pages: ";
		$maxpage = ceil($this->total / $this->COUNT_PER_PAGE);

		for ($i = 0; $i < $maxpage; $i++) {
			if ($i == $this->offset)
				$result .= $i . " ";
			else
				$result .= "<a href=\"?q=" . urlencode(h($this->keyword)) . "&offset=$i\">$i</a> ";
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
	<?php if ($msg['type'] == 'privmsg'): ?>
				<tr id="line<?=$msg['no']?>">
					<td class="time" title="<?=date('c', $msg['time'])?>"><a href="<?=$log->uri()?>#line<?=$msg['no']?>"><?=date('H:i:s', $msg['time'])?></a></td>
					<td class="nickname"><i>&lt;</i><?=!$msg['bot?'] ? h($msg['nick']) : '<strong>낚지</strong>'?><i>&gt;</i></td>
					<td class="message"><?=autolink(h($msg['text']))?></td>
				</tr>
	<?php elseif ($msg['type'] == 'join'): ?>
				<tr class="rejoin">
					<td class="time"><?=date('H:i:s', $msg['time'])?></td>
					<td class="nickname"><i>&lt;</i><?=!$msg['bot?'] ? h($msg['nick']) : '<strong>낚지</strong>'?><i>&gt;</i></td>
					<td class="message">** 낚지 부활! **</td>
				</tr>
	<?php endif; ?>
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
	<link rel="stylesheet" href="/style.css?v2" type="text/css">
	<script type="text/javascript" src="http://ajax.googleapis.com/ajax/libs/jquery/1.5/jquery.min.js"></script>
	<script type="text/javascript" src="http://log.langdev.org:8888/socket.io/socket.io.js"></script>
</head>
<body>
<div class="langdev__nav">
<div class="langdev__nav_inner">
<h3><a href="http://langdev.org/">LangDev</a></h3>
<ul>
<li><a href="http://langdev.org/posts/">Forum</a></li>
<li class="active"><a href="http://log.langdev.org/">Log</a></li>
<li><a href="http://topics.langdev.org/">Topics</a></li>
<li><a href="http://links.langdev.org/">Links</a></li>
<li><a href="http://docs.langdev.org/">Docs</a></li>
</ul>
</div>
</div>
<?php
}

/////////////////////////////

$path = trim(@$_SERVER['PATH_INFO'], '/');
if (empty($path)) {
	$log = Log::today();
	header("Location: " . $log->uri() . "?recent=30");
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
		$query = new SphinxSearchQuery(trim($_GET['q']));
		$query->offset = !empty($_GET['offset']) ? (int)$_GET['offset'] : 0;
		$result = $query->perform();
	} else
		$query = null;
?>
<?php print_header("search" . ($query ? ": $query->keyword" : '')); ?>
<h1>Log Search</h1>

<form method="get" action="">
	<p>어제까지의 기록을 검색합니다.</p>
	<p>검색어: <input type="text" name="q" value="<?=h($query->keyword)?>" /> <input type="submit" value="찾기" /></p>
	<?php if ($query and $query->message): ?>
	<p><?=$query->message?></p>
	<?php endif; ?>
</form>

<?php if ($query): ?>
<?php if (!empty($result)): ?>
<p><?=$query->paging()?></p>
<?php foreach ($result as $date => $messages): $log = new Log($date); ?>
<div class="day">
	<h2><a href="<?=$log->uri()?>"><?=$log->title()?></a></h2>
	<table>
		<?php print_lines($log, $messages); ?>
	</table>
</div>
<?php endforeach; ?>
<p><?=$query->paging()?></p>
<?php else: ?>
<p>검색 결과가 없습니다.</p>
<?php endif; ?>

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
		if ($only_recent = $log->is_today() && isset($_GET['recent'])) {
			$now = time();
			$from = 0;
			foreach ($messages as $i => $msg) {
				if (($now - $msg['time']) <= 60*$_GET['recent']) {
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
<div id="navbar">

<h2><?=$log->title()?></h2>
<p id="nav">
	<a href="/log/<?=date('Y-m-d', strtotime('yesterday'))?>">어제</a> &middot; <a href="/log/">오늘</a> &middot; <a href="/log/random">아무 날</a> / <a href="http://links.langdev.org/<?=vsprintf('%04d/%02d/%02d', $log->parsed_date())?>">링크</a> / <a href="#bottom">맨 아래로 &darr;</a>
</p>

<form method="get" action="search" id="search">
<p><input type="text" name="q" value="<?=h(@$query->keyword)?>" /> <input type="submit" value="찾기" /> / <a href="/log/atom">Atom 피드</a></p>
</form>
</div>

<div id="content">
<?php if ($only_recent): ?>
<p id="only-recent">최근 대화만 표시하고 있습니다. <a href="<?=$log->uri()?>">전체 보기</a> / <a href="<?=$log->uri()?>?recent=<?=$_GET['recent']+30?>">30분 더 보기</a></p>
<?php endif; ?>

<table>
<?php foreach (group_messages($messages) as $group): ?>
<tbody>
	<?php print_lines($log, $group); ?>
</tbody>
<?php endforeach; ?>
<tbody id="updates">
</tbody>
</table>

<?php if ($log->is_today()): ?>
<form method="post" action="say" id="say">
<p>
<input type="text" name="msg" id="msg" size="60" />
<input type="submit" value="보내기" />
<?=htmlspecialchars($_SERVER['PHP_AUTH_USER'])?>로 로그인 함
</p>
</form>

<script type="text/javascript">
var from = <?=$lines + 1?>;
var nickname = '<?=htmlspecialchars($_SERVER['PHP_AUTH_USER'])?>';

var socket = io.connect('http://log.langdev.org:8888');

socket.on('update', function () {
	_update_log();
});

function _update_log() {
	var _from = from;
	$.get('?from=' + _from, function (data) {
		if (from > _from) return;
		var willScroll = $(document).height() <= $(window).scrollTop()+$(window).height() + 20;
		$('#updates').append(data)
		if (willScroll)
			$(window).scrollTop($(document).height() + 100000)
	})
}

$('#say').submit(function(event) {
	socket.emit('msg', {nick: nickname, msg: $('#msg').val()});
	$('#msg').attr('value', '')
	event.preventDefault()
})
</script>
<?php else: ?>
<p id="eol">* 로그의 끝입니다. *</p>
<?php endif; ?>
</div>

<a name="bottom"></a>
</body>
</html>
<?php
	else:
		$messages = $log->messages((int)$_GET['from']);
		if (!empty($messages)) {
			$lines = $messages[count($messages)-1]['no'] + 1;
			print_lines($log, $messages);
			echo "<script>from=$lines</script>";
		}
	endif;
endif;
