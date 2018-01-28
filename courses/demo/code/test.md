markdown format tests
=====================

code
-----

```python
# Python code
for i in range(10):
    print i
```

```c
/* C code */
for (int i=0; i<20; i++){
  printf("The answer is %i\n", i);
}
```

```
# Generic code - no language specified.
define foo(x){
    return bar(x+1)
}
```

    This is an indented block.
      Four spaces at the   front
     of each      line.

image
-----

Images can be inserted with

![Jim and Cindy](https://cs.marlboro.college/images/jim_n_cin.jpeg) 

or since I allow html

<img src="https://cs.marlboro.college/images/jim_n_cin.jpeg" alt="Jim and Cindy">

text
----

Text with *one asterisk* or _one underscore_ or **two asterisks** or __two underscores__ .

Literal \* asterisks can be put in with backslash.


links
-----

These are reference-style links.
* [google][1]
* [Marlboro College][marlboro]

And these are the regular links
* [some company](http://somecompany.com)
* <http://somecompany.com>
  * bullet sublist : two spaces
* back to outer bullet scope.

The reference-style link definitions are typically at the end.

[1]: <http://www.google.com> "Google Inc"
[marlboro]: <https://www.marlboro.edu> "Marlboro College website"

