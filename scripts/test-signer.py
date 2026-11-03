import sys
import os
import argparse
import base64
import time
from cryptography.hazmat.primitives.asymmetric import ed25519

def generate_keypair():
    """Generates an ephemeral Ed25519 keypair and Minisign formatted pubkey."""
    priv = ed25519.Ed25519PrivateKey.generate()
    pub = priv.public_key()
    pub_raw = pub.public_bytes_raw()
    key_id = os.urandom(8)
    
    pub_bin = b'Ed' + key_id + pub_raw
    pub_b64 = base64.b64encode(pub_bin).decode('ascii')
    minisign_pub = f"untrusted comment: minisign public key: {key_id.hex().upper()}\n{pub_b64}\n"
    tauri_pubkey = base64.b64encode(minisign_pub.encode('utf-8')).decode('ascii')
    return priv, key_id, tauri_pubkey

def sign_package(priv_key, key_id, package_bytes, version="0.7.1"):
    """Signs package bytes producing a Minisign signature formatted for Tauri updater."""
    # 1. Primary signature over package bytes
    sig1 = priv_key.sign(package_bytes)
    bin1 = b'Ed' + key_id + sig1
    bin1_b64 = base64.b64encode(bin1).decode('ascii')

    # 2. Trusted comment with timestamp and version
    now = int(time.time())
    trusted_comment = f"trusted comment: timestamp:{now}\tversion:{version}\tfile:csm-modules-preview_{version}_x64_en-US.msi.zip"
    
    # 3. Global signature over (sig1 + trusted_comment)
    global_payload = sig1 + trusted_comment.encode('utf-8')
    global_sig = priv_key.sign(global_payload)
    bin2_b64 = base64.b64encode(global_sig).decode('ascii')

    minisign_sig_text = f"untrusted comment: signature from minisign secret key\n{bin1_b64}\n{trusted_comment}\n{bin2_b64}\n"
    tauri_sig_b64 = base64.b64encode(minisign_sig_text.encode('utf-8')).decode('ascii')
    return tauri_sig_b64, minisign_sig_text

def main():
    parser = argparse.ArgumentParser(description="Ephemeral Minisign Signer for Test Qualification")
    parser.add_argument("--package", required=True, help="Path to package to sign")
    parser.add_argument("--version", default="0.7.1", help="Version to record in trusted comment")
    parser.add_argument("--out-sig", help="Path to write signature file")
    parser.add_argument("--out-pub", help="Path to write pubkey file")
    args = parser.parse_args()

    with open(args.package, "rb") as f:
        pkg_bytes = f.read()

    priv, key_id, pubkey = generate_keypair()
    sig_b64, sig_text = sign_package(priv, key_id, pkg_bytes, args.version)

    print(f"Key ID: {key_id.hex().upper()}")
    print(f"Tauri Pubkey:\n{pubkey}")
    print(f"Tauri Signature:\n{sig_b64}")

    if args.out_pub:
        with open(args.out_pub, "w", encoding="utf-8") as f:
            f.write(pubkey)
    if args.out_sig:
        with open(args.out_sig, "w", encoding="utf-8") as f:
            f.write(sig_b64)

if __name__ == "__main__":
    main()
