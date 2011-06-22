<?php
/*
 * #langdev xmlpipe2 driver for sphinxsearch
 */

ini_set('display_errors', 'Off');

function messages($filename) {
	$fp = @fopen($filename, 'r');
	if (!$fp)
		return;
	$no = 0;
	while ($line = fgets($fp)) {
		if (preg_match('/PRIVMSG/', $line)) {
			$no++;
			if (!preg_match('/^.*?\[(.+?)(?: #.*?)?\].*? (<<<|>>>) (?::(.+?)!.+? )?PRIVMSG #.+? :(.+)$/', $line, $parts))
				continue;
			$is_bot = !$parts[3];

			if ($is_bot && preg_match('/^<(.+?)> (.*)$/', $parts[4], $tmp)) {
				$parts[3] = $tmp[1];
				$parts[4] = $tmp[2];
				$is_bot = false;
			}

			print2xml(array(
				'no' => $no,
				//'time' => strtotime($parts[1]),
				'time' => $parts[1],
				'nick' => $parts[3],
				'text' => $parts[4],
				'bot?' => $is_bot,
			));
		}
	}
	fclose($fp);
}

// this is overflow in 32 bits
// need "--enable-id64" compile option of sphinxsearch
function unique_id($time, $lineno) {
	$d = split("-", substr($time, 0, 10));
	return "{$d[0]}{$d[1]}{$d[2]}" . sprintf("%08d", $lineno);
}

function print2xml($arr) {
	$id = unique_id($arr['time'], $arr['no']);
	$content = htmlspecialchars($arr['text'], ENT_QUOTES | ENT_IGNORE, "UTF-8");
	//$content = $arr['text'];
	$nick = $arr['nick'];
	$time = strtotime($arr['time']);
	$lineno = $arr['no'];
	$bot = $arr['bot?'] ? 1 : 0;

	echo "<sphinx:document id=\"$id\">
\t<content>$content</content>
\t<no>$lineno</no>
\t<nick>$nick</nick>
\t<time>$time</time>
\t<bot>$bot</bot>
</sphinx:document>
";
}

if ($argc < 2) {
	fwrite(STDERR, "Usage: php log2xml.php [files]...\n");
	return -1;
}
else {
	array_splice($argv, 0, 1);

	echo '<?xml version="1.0" encoding="utf-8"?>
<sphinx:docset>
<sphinx:schema>
	<sphinx:field name="content" attr="string"/>
	<sphinx:attr name="no" type="int" bits="32"/>
	<sphinx:attr name="nick" type="string"/>
	<sphinx:attr name="time" type="timestamp"/>
	<sphinx:attr name="bot" type="bool"/>
</sphinx:schema>
';

	foreach ($argv as $ar)
		messages($ar);

	echo "</sphinx:docset>\n";
}

?>

