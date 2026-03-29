# Capstone mTLS Explainer

This note summarizes the mTLS concepts we worked through for this project, using the repo's actual files and current setup.

## 1. Current Project Snapshot

- MQTT broker: laptop-hosted Mosquitto
- TLS MQTT port: `8883`
- Plain MQTT port: `1883` for optional local development
- mTLS is enabled on `8883`, so the broker requires client certificates
- Current broker SANs include `172.20.10.3`

Relevant files:

- Broker TLS config: `Comms/mosquitto/mosquitto.conf`
- Broker cert SAN settings: `Comms/mosquitto/certs/server.ext`
- Current broker cert: `Comms/mosquitto/certs/server.crt`
- CA cert: `Comms/mosquitto/certs/ca.crt`
- Headset client cert: `Comms/mosquitto/certs/clients/headset.crt`
- Headset private key: `Comms/mosquitto/certs/clients/headset.key`
- Unity bundle: `Comms/visualizer/unity_fix_bundle/`

Current broker TLS configuration:

```text
listener 8883
cafile /mosquitto/config/certs/ca.crt
certfile /mosquitto/config/certs/server.crt
keyfile /mosquitto/config/certs/server.key
require_certificate true
```

That means:

1. The broker presents `server.crt` to clients.
2. The broker proves it owns `server.key`.
3. Clients must present their own certificate and prove they own the matching private key.

## 2. What Each File Actually Is

### CA files

- `ca.key`
  The CA private key. This is the master signing secret. It must stay private.
- `ca.crt`
  The CA public certificate. This is shared to every component that must trust certificates issued by this CA.
- `ca.srl`
  A serial counter OpenSSL uses when issuing certificates.

### Broker files

- `server.key`
  The broker's private key. Only the broker should hold this.
- `server.csr`
  The broker's Certificate Signing Request. This is only used while issuing the broker cert.
- `server.crt`
  The broker's identity certificate, signed by the CA.
- `server.ext`
  Extra certificate settings for the broker cert, especially hostname and IP SAN entries.

### Client files

For a client such as `headset`, `left_glove`, `right_glove`, `simulator`, `unity_pub`:

- `<name>.key`
  The client's private key. Secret.
- `<name>.csr`
  The client's certificate request. Temporary issue-time artifact.
- `<name>.crt`
  The client's identity certificate, signed by the CA.
- `<name>.pfx`
  A packaged file that contains a client cert and private key together. Unity uses this format.

### ESP32-specific note

The ESP32 devices do not read `.crt` and `.key` files directly at runtime.

Instead, the CA cert, client cert, and private key are embedded into `certs.h`, then loaded in code like this:

```cpp
espClient.setCACert(CA_CERT);
espClient.setCertificate(CLIENT_CERT);
espClient.setPrivateKey(CLIENT_KEY);
```

This is how the headset, gloves, and other ESP32 devices use mTLS in this repo.

## 3. Who Holds What

### Broker on laptop

The broker holds:

- `ca.crt`
- `server.crt`
- `server.key`

Why:

- `server.crt` + `server.key` let the broker prove its identity
- `ca.crt` lets the broker verify client certificates

### Headset ESP32

The headset holds:

- CA cert
- headset client certificate
- headset private key

In this repo they are compiled into the firmware through `Hardware/Headset/certs.h`.

Why:

- CA cert lets the headset verify the broker
- headset cert + headset key let the headset prove its identity to the broker

### Unity visualiser

Unity holds:

- `ca.crt`
- `unity_pub.pfx`

Why:

- `ca.crt` verifies the broker
- `unity_pub.pfx` gives Unity a client cert and matching private key

### Ultra96

Ultra96 holds:

- `ca.crt`
- `simulator.crt`
- `simulator.key`

Why:

- Same reason as other clients: trust broker, then authenticate to broker

### CA machine or signing environment

Only the certificate issuer should hold:

- `ca.key`

Do not distribute `ca.key` to clients or broker runtime environments.

## 4. Why Both Broker and Headset Hold `ca.crt`

Because mTLS has trust in both directions.

- The headset uses `ca.crt` to verify the broker's `server.crt`
- The broker uses `ca.crt` to verify the headset's `headset.crt`

`ca.crt` is public and safe to distribute.

`ca.key` is private and must not be distributed.

Short version:

- `ca.crt` = the public trust anchor
- `ca.key` = the secret signing authority

## 5. What a CSR Is

CSR means Certificate Signing Request.

It is not a runtime identity file. It is only used during certificate issuance.

For a headset:

```text
headset.key -> headset.csr -> signed by CA -> headset.crt
```

What a CSR contains:

- the client's public key
- the requested subject name, for example `CN=headset`
- optional metadata

What it does not contain:

- a usable signed certificate
- the CA signature
- the private key

In this repo, the client cert creation flow is visible in `Comms/mosquitto/gen_client_cert.sh`:

1. generate private key
2. generate CSR
3. sign CSR with `ca.key`
4. output final certificate

## 6. The Whole Headset-to-Broker mTLS Flow

This is the actual connection logic for the headset.

### Step 1: headset loads its TLS material

The headset firmware loads:

- CA cert
- headset client cert
- headset private key

### Step 2: headset opens a TLS connection to broker `:8883`

The broker is configured to require certificates on `8883`.

### Step 3: broker sends `server.crt`

The headset receives the broker certificate.

### Step 4: headset verifies broker identity

The headset checks:

1. Was `server.crt` signed by the CA trusted in `ca.crt`?
2. Is the certificate still within its validity dates?
3. Does the certificate identity match the hostname or IP the headset connected to?

This last part is why `server.ext` matters. If the client connects to an IP that is not in the broker cert SAN list, TLS fails even if the cert is otherwise real.

### Step 5: broker requests a client certificate

Because `require_certificate true` is enabled, the broker asks the headset to authenticate itself.

### Step 6: headset sends `headset.crt`

Now the broker has the headset's public identity certificate.

But the broker does not trust the certificate alone, because anyone can copy a public certificate file.

### Step 7: headset proves it owns `headset.key`

The TLS library on the headset signs handshake data using the private key.

The headset does not send `headset.key`.

Instead it sends a fresh digital signature created with that private key.

### Step 8: broker verifies that signature using the public key in `headset.crt`

If verification succeeds:

- the broker trusts that the headset actually owns the private key
- so the broker trusts that the headset is the legitimate owner of `headset.crt`

### Step 9: secure MQTT session starts

Only after both checks pass:

- headset trusts broker
- broker trusts headset

Then MQTT publish/subscribe can begin over the encrypted TLS channel.

## 7. Two Different Signatures

This was the biggest conceptual trap in the discussion.

There are two different signatures in the system.

### A. CA signature on a certificate

Example:

- the CA signs `headset.crt`
- the CA also signs `server.crt`

Purpose:

- prove that the certificate was issued by the CA

This signature is stored inside the certificate itself.

When you run:

```bash
openssl x509 -in Comms/mosquitto/certs/clients/headset.crt -noout -text
```

the `Signature Value:` you see is this CA-issued certificate signature.

### B. TLS handshake signature proving private key ownership

During a live TLS session:

- the headset signs the handshake transcript with `headset.key`
- the broker verifies using the public key inside `headset.crt`

Purpose:

- prove that the client actually owns the private key for the presented certificate

This signature is not stored on disk as a file.

It is generated fresh for each connection and sent as part of the TLS handshake.

## 8. How the TLS Proof of Ownership Works

Short version:

- private key signs
- public key verifies

### Conceptual flow

1. Both sides have seen the same handshake bytes so far.
2. Both sides compute a hash of that handshake transcript.
3. The client uses its private key to sign that hash.
4. The broker uses the public key from the client's certificate to verify the signature.

If it verifies, the broker knows the client has the real private key.

### Why this matters

Anyone can copy `headset.crt`.

But without `headset.key`, they cannot create a valid handshake signature that matches the public key in that cert.

## 9. The RSA Math Behind It

Your current headset certificate and key use RSA-2048.

That means the keypair is built like this:

1. Pick two large primes `p` and `q`
2. Compute:

```text
n = p * q
```

3. Compute a totient-like value:

```text
phi(n) = (p - 1)(q - 1)
```

4. Choose a public exponent `e`

In your keys this is:

```text
e = 65537
```

5. Compute the private exponent `d` so that:

```text
e * d ≡ 1 mod phi(n)
```

The RSA public key is:

```text
(n, e)
```

The RSA private key is essentially:

```text
d
```

### Why the public key is `(n, e)`

Because RSA verification is defined using:

```text
x^e mod n
```

So the verifier needs:

- the modulus `n`
- the public exponent `e`

Those two numbers are the public key.

### Signature math

RSA does not sign the raw message directly.

It signs an encoded hash of the message.

Let:

- `T` = the TLS handshake transcript
- `h = SHA256(T)`
- `EM` = the properly padded encoding of `h`
- `m` = integer interpretation of `EM`

Then the signature is:

```text
s = m^d mod n
```

The broker verifies using:

```text
m' = s^e mod n
```

Then it decodes `m'` and checks whether the recovered hash equals the expected hash it computed itself from the same transcript.

If yes, the signature is valid.

### Short clean version

Signing:

```text
signature = Sign(private_key, SHA256(handshake_transcript))
```

Verification:

```text
Verify(public_key, SHA256(handshake_transcript), signature)
```

## 10. What "Valid Signature" Actually Means

It does not mean:

- "sign it with the public key again"
- "encrypt it again with the public key"

It means:

- the verifier computes the expected hash from the actual handshake bytes
- the verifier uses the public key to check whether the provided signature corresponds to that exact hash

If it does, then only the matching private key could have created it.

## 11. Why Replays Do Not Work

The client signs the current handshake transcript.

That transcript changes each session because TLS includes fresh random values and fresh connection state.

So an attacker cannot simply record an old signature and reuse it later.

## 12. What `.pfx` Means for Unity

Unity uses a `.pfx` file because it is a convenient container format that bundles:

- client certificate
- private key
- optionally CA chain

In this repo:

- Unity uses `unity_pub.pfx`
- the password is `capstone`

Unity also separately uses `ca.crt` to verify the broker.

## 13. What Fails When Something Is Wrong

### Wrong `ca.crt`

Result:

- client cannot trust broker cert
- broker cannot trust client cert

### Wrong hostname/IP

Result:

- certificate chain may still be valid
- TLS still fails because identity does not match

Example:

- broker cert SAN includes `172.20.10.3`
- client connects to `172.20.10.13`
- TLS identity check fails

### Wrong private key for a certificate

Result:

- proof-of-ownership signature fails
- broker rejects the client

### Missing Unity `.pfx`

Result:

- Unity cannot present its client cert and private key
- mTLS connection fails on port `8883`

### Wrong `.pfx` password

Result:

- Unity cannot load the private key from the PFX
- MQTT connection setup fails before or during TLS initialization

## 14. What To Regenerate in Common Situations

### If broker IP or hostname changes but CA stays the same

Do this:

1. edit `Comms/mosquitto/certs/server.ext`
2. reissue only the broker server cert
3. restart Mosquitto

Do not regenerate:

- `ca.crt`
- `ca.key`
- client certificates
- `Hardware/certs.h`

### If the CA changes

You must regenerate and redistribute everything signed by the old CA:

- broker cert
- all client certs
- Unity PFX
- ESP32 embedded cert bundle
- Ultra96 client certs

### If only a Unity client bundle is stale

Regenerate only Unity client certs:

- `unity_pub.crt`
- `unity_pub.key`
- `unity_pub.pfx`

and refresh:

- `ca.crt`
- `unity_pub.pfx`

inside the Unity project

## 15. Reverse SSH Tunnel and mTLS

The Ultra96 reverse SSH tunnel does not replace TLS and does not change the certificate logic.

It only forwards bytes.

Working mental model:

```text
Ultra96 localhost:18883 --SSH tunnel--> laptop broker :8883
```

The TLS handshake still happens end-to-end between:

- Ultra96 MQTT client
- laptop Mosquitto broker

So Ultra96 still needs:

- `ca.crt`
- `simulator.crt`
- `simulator.key`

and the broker still requires client authentication on `8883`.

## 16. Useful Commands

Inspect a certificate:

```bash
openssl x509 -in Comms/mosquitto/certs/server.crt -noout -text
```

Inspect SANs:

```bash
openssl x509 -in Comms/mosquitto/certs/server.crt -noout -ext subjectAltName
```

Inspect a client certificate:

```bash
openssl x509 -in Comms/mosquitto/certs/clients/headset.crt -noout -subject -issuer -dates
```

Inspect a private key:

```bash
openssl rsa -in Comms/mosquitto/certs/clients/headset.key -text -noout
```

Verify a Unity PFX against the current CA:

```bash
Comms/mosquitto/check_client_pfx.sh \
  Comms/mosquitto/certs/clients/unity_pub.pfx \
  capstone \
  Comms/mosquitto/certs/ca.crt
```

Reissue only the server cert after a broker IP or hostname change:

```bash
Comms/mosquitto/reissue_server_cert.sh
```

## 17. Short Presentation Version

If you need to explain this in class:

1. The CA creates trust for the whole system.
2. The broker gets a server certificate signed by the CA.
3. Each client gets its own client certificate signed by the CA.
4. Both client and broker store `ca.crt` so they can verify each other.
5. The client proves it owns its private key by signing the TLS handshake.
6. The broker verifies that signature using the public key in the client certificate.
7. If both sides trust each other, the MQTT/TLS connection is established.
