# Advanced example

Now we're using a more complicated example of a server:

- server requires a login to do anything - need to save the token it returns and
  use for future authorization
- using a database - persistent storage that will be there between stages of tests

Now we use multiple stages of tests in a row and make sure that the server state
has been updated as expected between each one.
