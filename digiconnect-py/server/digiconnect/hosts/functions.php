<?php
/* DigiConnect — host-file helpers shared by refresh.php, get.php and the admin panel. */
require_once __DIR__ . '/../lib.php';

if (!function_exists('fetch_url')) {
function fetch_url(string $url, int $timeout = 25, ?string &$why = null): ?string {
  $why = '';
  if (function_exists('curl_init')) {
    $ch = curl_init($url);
    curl_setopt_array($ch, [CURLOPT_RETURNTRANSFER=>true, CURLOPT_FOLLOWLOCATION=>true, CURLOPT_MAXREDIRS=>5, CURLOPT_TIMEOUT=>$timeout,
      CURLOPT_CONNECTTIMEOUT=>12, CURLOPT_USERAGENT=>'DigiConnect-HostSync/1.1 (SA7SVR)', CURLOPT_SSL_VERIFYPEER=>true]);
    $body = curl_exec($ch); $code = (int)curl_getinfo($ch, CURLINFO_HTTP_CODE); $err = curl_error($ch); curl_close($ch);
    if ($body === false) { $why = 'curl: ' . $err; return null; }
    if ($code < 200 || $code >= 300) { $why = "HTTP $code"; return null; }
    return (string)$body;
  }
  $ctx = stream_context_create(['http'=>['timeout'=>$timeout,'user_agent'=>'DigiConnect-HostSync/1.1'], 'ssl'=>['verify_peer'=>true]]);
  $body = @file_get_contents($url, false, $ctx);
  if ($body === false) { $why = 'download failed'; return null; }
  return $body;
}
}

/* A host file must look like a host file, not an HTML error page or an empty reply. */
function hosts_valid(string $body, string &$why): bool {
  $head = strtolower(substr(ltrim($body), 0, 200));
  if (strpos($head, '<html') !== false || strpos($head, '<!doctype') !== false) { $why = 'HTML page instead of a list'; return false; }
  $n = 0;
  foreach (preg_split('/\r?\n/', $body) as $ln) { $ln = trim($ln); if ($ln !== '' && $ln[0] !== '#') $n++; }
  if ($n < 3) { $why = "only $n entries"; return false; }
  return true;
}

/* Where lists are stored. data/hosts is always writable (the database lives in data/); hosts/pub is a best-effort public copy. */
function hosts_store_dirs(): array {
  $dirs = [__DIR__ . '/pub', dirname(dc_cfg()['db']) . '/hosts'];
  foreach ($dirs as $d) if (!is_dir($d)) @mkdir($d, 0775, true);
  return $dirs;
}
function hosts_write_atomic(string $path, string $data, string &$why): bool {
  $dir = dirname($path);
  if (!is_dir($dir)) { $why = "folder missing: $dir"; return false; }
  if (!is_writable($dir)) { $why = "not writable: $dir"; return false; }
  $tmp = $path . '.tmp';
  if (@file_put_contents($tmp, $data, LOCK_EX) === false) { $e = error_get_last(); $why = 'write failed: ' . ($e['message'] ?? $tmp); return false; }
  if (!@rename($tmp, $path)) { @unlink($tmp); $why = "rename failed: $path"; return false; }
  @chmod($path, 0644);
  if (!is_file($path) || filesize($path) !== strlen($data)) { $why = "verify failed: $path"; return false; }
  return true;
}
function hosts_count_lines(string $path): int {
  if (!is_file($path)) return 0;
  $n = 0; $h = @fopen($path, 'r'); if (!$h) return 0;
  while (($ln = fgets($h)) !== false) { $ln = trim($ln); if ($ln !== '' && $ln[0] !== '#') $n++; }
  fclose($h); return $n;
}
/* The copy the app and the panel use: hosts/pub first, else data/hosts. */
function hosts_find(string $file): ?string {
  foreach ([__DIR__ . '/pub', dirname(dc_cfg()['db']) . '/hosts'] as $d) if (is_file("$d/$file") && filesize("$d/$file") > 0) return "$d/$file";
  return null;
}

