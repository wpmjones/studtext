var el;

function count_characters(e)  {
  var text_entered, text_length, count_remaining, num_msg, counter;
  text_entered = document.getElementById('msg').value;
  text_length = text_entered.length;
  if (text_length <= 160) {
    counter = (160 - text_length);
  } else {
    num_msg = parseInt(text_length/160) + 1;
    counter = '(' + num_msg + ' messages) ' + (160 - (text_length % 160))
  };
  count_remaining = document.getElementById('remaining');
  count_remaining.textContent = counter + '/160 remaining';
}

el = document.getElementById('msg');
el.addEventListener('keyup', count_characters, false);
