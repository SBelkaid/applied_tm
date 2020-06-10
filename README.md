Applied Text Mining
=============

Description
----------
This is a school project in which multiple files needed to be parsed. The format of the source files is CoNLL and NAF.

Installation
-----------
Clone the repository from github

````shell
git clone git@github.com/SBelkaid/applied_tm.git

````
create a virtualenv 

```shell
python3 -m venv atm-venv
```

Install the requirements.txt file using pip
````shell

cat requirements.txt | xargs -n 1 pip install

````

Usage
-----
call the parser.py script with he paths to the directories containing the source files.

```shell

NameOfComputer: python parser.py conll-allen-nlp naf-newsreader-nlp

```

Running the flask-server, will serve the flask-app on http://127.0.0.1:8999/


```shell

NameOfComputer: python app.py

```


Results
-------------
parser.py generates sqlite.db a database file containing parsed information from the NAF and CoNLL files. One can use the dbsqlitebrowser to browse
through the data or use sql statements to query the tables.

![alt tag](https://github.com/SBelkaid/applied_tm/blob/master/perspectives.png)


Contact
------

* Soufyan Belkaid
* s.belkaid@student.vu.nl
* Vrije University of Amsterdam

License
------
nothing special
