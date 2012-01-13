(function ($) {

var content = $('#content');
content.delegate('.nickname', 'click', function (e) {
  var row = $(this).parent(),
      userid = row.data('userid'),
      selected = row.hasClass('selected');
  content.find('tr').removeClass('selected');
  if (!selected) {
    content.find('tr[data-userid="' + userid +'"]')
           .addClass('selected');
  }
});

}(jQuery));
