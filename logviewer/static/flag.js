var flag_mode = false;
var flags = [];
function toggle_flag_mode(mode) {
    flag_mode = !flag_mode;
    if (flag_mode) {
    	$('.time a').addClass('flaggable').click(function () {
    		var time = $(this).text();
    		var line = $(this).closest('tr').attr('id').substring(4);
    		var title = prompt('Enter flag title');
    		if (title != null)
    			$.post(location.pathname + '/' + line + '/flags', {time: time, title: title},
    			    function(id) {
                    	add_flag({line: line, time: time, title: title, id: id, user: nickname});
                    });
        });
    } else {
    	$('.time a').removeClass('flaggable').unbind('click');
    }

    var btn = $('#toggle-flag-mode');
    var desc = $('#flag-mode-desc');
    if (!flag_mode) {
        btn.text('깃발 꽂기');
        desc.hide();
    } else {
        btn.text('깃발 그만 꽂기');
        desc.show();
    }
}
function add_flag(item) {
    flags.push(item);
    flags.sort(function(a, b) { return parseInt(a.line) - parseInt(b.line); });
    redraw_flags();
}
function redraw_flags() {
	$('#flags ul').html('');
	if (flags.length > 0)
        $.each(flags, function (i, item) {
            $('#flags ul').append('<li>' + item.time + ' <a href="#line' + item.line + '">' + item.title + '</a></li>');
        });
    else
    	$('#flags ul').html('<li>아직 깃발이 하나도 없네요.</li>');
}
$(function() {
	$('#toggle-flag-mode').click(function () {
		toggle_flag_mode();
		return false;
    });
	$.getJSON(location.pathname + '/flags', function (data) {
		flags = data;
		redraw_flags();
    });
});
