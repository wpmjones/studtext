var el;

function countCharacters(e)  {
  var textEntered, countRemaining, counter;
  textEntered = document.getElementById('tweet').value;
  counter = (160 - (textEntered.length));
  countRemaining = document.getElementById('remaining');
  countRemaining.textContent = counter + '/160 remaining';
}

el = document.getElementById('remaining');
el.addEventListener('keyup', countCharacters, false);

