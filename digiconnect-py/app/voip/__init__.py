"""DigiConnect VoIP: a SIP telephone for the HELLAS Zone VoIP server (and any other SIP PBX).

It is written for the standards (RFC 3261 SIP, RFC 3550/3551 RTP and G.711, RFC 4733 DTMF, RFC 4235 / RFC 3856 for who is busy or online) and it is
checked against a real PBX (Asterisk), not only against code of our own. Nothing is simulated: a state shown in the program is a state the server
sent (registered, ringing, busy, ...), and when the server says nothing the program says "unknown"."""
