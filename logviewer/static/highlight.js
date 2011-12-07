(function ($) {

var content = $('#content');
content.delegate('td.nickname > span', 'click', function (e) {
  var self = $(this),
      row = self.closest('tr'),
      userid = row.data('userid'),
      selected = row.hasClass('selected');
  content.find('tr').removeClass('selected');
  if (!selected) {
    content.find('tr[data-userid="' + userid +'"]')
           .addClass('selected');
  }
});

}(jQuery));
