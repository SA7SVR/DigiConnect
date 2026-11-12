<?php
// DigiConnect — PayPal Instant Payment Notification (IPN), same as HAM Digi. PayPal calls this address after every payment/donation.
// Set it in PayPal: Account Settings › Notifications › Instant payment notifications › https://hellaszone.com/digiconnect/ipn.php
// The PayPal account is shared with HAM Digi: PayPal has ONE address per account, so HAM Digi's ipn.php forwards a copy here (see ΔΙΑΒΑΣΕ-ΜΕ.txt).
require __DIR__ . '/lib.php';
header('Content-Type: text/plain; charset=utf-8');
$raw = file_get_contents('php://input');
if ($raw === '' || $_SERVER['REQUEST_METHOD'] !== 'POST') { echo 'DigiConnect IPN listener — OK'; exit; }
$S = dc_pay_settings();
// 1) ask PayPal whether this message is genuine (a forwarded copy is checked again, so nobody can invent a payment)
$url = $S['sandbox'] ? 'https://ipnpb.sandbox.paypal.com/cgi-bin/webscr' : 'https://ipnpb.paypal.com/cgi-bin/webscr';
$body = 'cmd=_notify-validate&' . $raw; $res = '';
if (function_exists('curl_init')) {
  $c = curl_init($url); curl_setopt_array($c, [CURLOPT_POST => 1, CURLOPT_POSTFIELDS => $body, CURLOPT_RETURNTRANSFER => 1, CURLOPT_TIMEOUT => 30, CURLOPT_SSL_VERIFYPEER => 1, CURLOPT_HTTPHEADER => ['Connection: Close', 'User-Agent: DigiConnect-IPN']]);
  $res = (string)curl_exec($c); curl_close($c);
} else {
  $res = (string)@file_get_contents($url, false, stream_context_create(['http' => ['method' => 'POST', 'header' => "Content-Type: application/x-www-form-urlencoded\r\nUser-Agent: DigiConnect-IPN\r\n", 'content' => $body, 'timeout' => 30]]));
}
parse_str($raw, $p);
$enc = strtolower($p['charset'] ?? 'utf-8'); if ($enc !== 'utf-8' && function_exists('mb_convert_encoding')) foreach ($p as $k => $v) $p[$k] = @mb_convert_encoding((string)$v, 'UTF-8', $enc);
if (trim($res) !== 'VERIFIED') { dc_event('pay_invalid', substr(trim($res), 0, 40) . '|' . substr((string)($p['txn_id'] ?? ''), 0, 30)); http_response_code(200); echo 'not verified'; exit; }
echo dc_ipn_process($p, $raw, $S);
