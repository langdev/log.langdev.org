(function ($) {

var content = $('#content');
content.delegate('tr', 'click', function (e) {
  var self = $(this),
      userid = self.data('userid'),
      selected = self.hasClass('selected');
  content.find('tr').removeClass('selected');
  if (!selected) {
    content.find('tr[data-userid="' + userid +'"]')
           .addClass('selected');
  }
});

}(jQuery));
