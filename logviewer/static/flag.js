var flags = [];
function add_flag(item) {
    flags.push(item);
    flags.sort(function(a, b) { return parseInt(a.line) - parseInt(b.line); });
    redraw_flags();
}
function redraw_flags() {
	$('#flags').html('');
	if (flags.length > 0)
        $.each(flags, function (i, item) {
            $('#flags').append('<li><a href="' + location.pathname + '#line' + item.line + '"><span class="time">' + item.time + '</span> ' + item.title + '</a></li>');
        });
    $('#flags').append('<li id="add-flag-link"><a href="#">깃발 추가...</a></li>');
}
function refresh_flags() {
	$.getJSON(location.pathname + '/flags', function (data) {
		flags = data;
		redraw_flags();
    });
}

var inFlagMode = false;
function beginFlagMode() {
    if (inFlagMode) return;
    inFlagMode = true;
    $('#flag-mode-desc').fadeIn('fast');
    $('.time a').addClass('flaggable');
    $('#content').on('click', '.time a', function() {
        var time = $(this).text();
        var line = $(this).closest('tr').attr('id').substring(4);
        var title = prompt('Enter flag title');
        if (title)
            $.post(location.pathname + '/' + line + '/flags', {time: time, title: title},
                function(id) {
                    add_flag({line: line, time: time, title: title, id: id, user: window.NICKNAME});
                    alert('추가됨');
                });
        return false;
    });
}
function endFlagMode() {
    if (!inFlagMode) return;
    inFlagMode = false;
    $('#flag-mode-desc').fadeOut('fast');
    $('.time a').removeClass('flaggable');
    $('#content').off('click', '.time a');
}
$(function() {
    $('#flags').on('click', '#add-flag-link', function() {
        beginFlagMode();
        $('#flags').dropdown('toggle'); // hide dropdown
        return false;
    });
    refresh_flags();
});
