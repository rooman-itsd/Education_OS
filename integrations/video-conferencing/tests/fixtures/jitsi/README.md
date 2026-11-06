Jitsi has no provider API to record: a room is a name and a join link is a JWT we sign. The tests decode those tokens with the
test secret and check the claims against lib-jitsi-meet's documented token format (iss, aud, sub, room, exp, context.user).
`docker-jitsi-meet` with JWT auth is the live check (tests/test_live_jitsi.py, skipped unless VIDEO_CONFERENCING_TEST_JITSI_URL is set).
