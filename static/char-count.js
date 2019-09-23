console.log('Start js')
var el;

function countCharacters(e)  {
  console.log('Inside function')
  var textEntered, countRemaining, counter;
  textEntered = document.getElementById('msg').value;
  counter = (160 - (textEntered.length));
  console.log(counter)
  countRemaining = document.getElementById('remaining');
  countRemaining.textContent = counter + '/160 remaining';
}

el = document.getElementById('msg');
el.addEventListener('keyup', countCharacters, false);
console.log('Event Listener created')