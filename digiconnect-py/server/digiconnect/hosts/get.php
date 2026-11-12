<?php
/* Serves a host list from hosts/pub, or from data/hosts when hosts/pub is not writable by the web server.
   Use:  hosts/get.php?f=YSFHosts.txt   (the direct hosts/pub/<file> URL keeps working when that folder is writable) */
require_once __DIR__ . '/functions.php';
$SOURCES = require __DIR__ . '/sources.php';
$f = (string)($_GET['f'] ?? '');
if (!isset($SOURCES[$f])) { http_response_code(404); header('Content-Type: text/plain'); exit("unknown list\n"); }
$p = hosts_find($f);
if (!$p) { http_response_code(404); header('Content-Type: text/plain'); exit("list not downloaded yet\n"); }
header('Content-Type: text/plain; charset=utf-8'); header('Cache-Control: public, max-age=300'); header('Content-Length: ' . filesize($p));
readfile($p);
