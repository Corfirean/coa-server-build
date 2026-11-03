import sys
import os
import argparse
import base64
import json
from pathlib import Path
from cryptography.hazmat.primitives.asymmetric import ed25519
from cryptography.exceptions import InvalidSignature

def parse_minisign_pubkey(pubkey_str):
    """Parses a Minisign public key from base64 string or raw text."""
    pubkey_str = pubkey_str.strip()
    # If base64 encoded text (like Tauri's pubkey config)
    if not pubkey_str.startswith("untrusted comment:"):
        try:
            decoded = base64.b64decode(pubkey_str).decode("utf-8")
            if "untrusted comment:" in decoded:
                pubkey_str = decoded.strip()
        except Exception:
            pass

    lines = [l.strip() for l in pubkey_str.splitlines() if l.strip()]
    if len(lines) < 2:
        # Check if single line raw base64 (42 bytes: 2 'Ed' + 8 key_id + 32 pubkey)
        raw = base64.b64decode(pubkey_str)
        if len(raw) == 42:
            return raw[:2], raw[2:10], raw[10:]
        elif len(raw) == 32:
            return b'Ed', b'\x00' * 8, raw
        raise ValueError(f"Malformed public key text: expected at least 2 lines or valid base64, got {len(lines)} lines")

    b64_key = lines[1]
    raw = base64.b64decode(b64_key)
    if len(raw) != 42:
        raise ValueError(f"Malformed public key: expected 42 decoded bytes, got {len(raw)}")
    
    sig_alg = raw[:2]
    key_id = raw[2:10]
    pub_bytes = raw[10:]
    return sig_alg, key_id, pub_bytes

def parse_minisign_signature(sig_str):
    """Parses a Minisign signature from 4-line text or base64 wrapper."""
    sig_str = sig_str.strip()
    if not sig_str.startswith("untrusted comment:"):
        try:
            decoded = base64.b64decode(sig_str).decode("utf-8")
            if "untrusted comment:" in decoded:
                sig_str = decoded.strip()
        except Exception:
            pass

    lines = [l.strip() for l in sig_str.splitlines() if l.strip()]
    if len(lines) < 4:
        raise ValueError(f"Malformed signature: expected 4 lines, got {len(lines)}")

    # Line 1: untrusted comment
    untrusted_comment = lines[0]
    # Line 2: base64(2 bytes 'Ed' + 8 bytes key_id + 64 bytes signature)
    bin1 = base64.b64decode(lines[1])
    if len(bin1) != 74:
        raise ValueError(f"Malformed signature line 2: expected 74 bytes, got {len(bin1)}")
    
    sig_alg = bin1[:2]
    sig_key_id = bin1[2:10]
    sig_raw = bin1[10:]

    # Line 3: trusted comment
    trusted_comment = lines[2]
    if not trusted_comment.startswith("trusted comment:"):
        raise ValueError("Malformed signature line 3: missing 'trusted comment:' prefix")

    # Line 4: base64(64 bytes global signature)
    global_sig = base64.b64decode(lines[3])
    if len(global_sig) != 64:
        raise ValueError(f"Malformed signature line 4: expected 64 bytes, got {len(global_sig)}")

    return {
        "sig_alg": sig_alg,
        "key_id": sig_key_id,
        "sig_bytes": sig_raw,
        "trusted_comment": trusted_comment,
        "global_sig": global_sig
    }

def verify_updater_signature(pubkey_str, package_bytes, signature_str, announced_version=None):
    """Full cryptographic verification of Tauri updater signature."""
    if not signature_str:
        raise ValueError("Signature string is empty. Cryptographic verification cannot proceed.")
    if not package_bytes:
        raise ValueError("Package bytes are empty.")

    # 1. Parse public key
    sig_alg, key_id, pub_bytes = parse_minisign_pubkey(pubkey_str)
    try:
        verifier_pubkey = ed25519.Ed25519PublicKey.from_public_bytes(pub_bytes)
    except Exception as e:
        raise ValueError(f"Failed to load Ed25519 public key: {e}")

    # 2. Parse signature
    sig_info = parse_minisign_signature(signature_str)

    # 3. Verify Key ID matching
    if key_id != (b'\x00' * 8) and sig_info["key_id"] != key_id:
        raise ValueError(
            f"Key ID mismatch: signature was created with key {sig_info['key_id'].hex().upper()}, "
            f"expected {key_id.hex().upper()}"
        )

    # 4. Verify primary signature over package bytes
    try:
        verifier_pubkey.verify(sig_info["sig_bytes"], package_bytes)
    except InvalidSignature:
        raise ValueError("CRYPTOGRAPHIC VERIFICATION FAILED: Ed25519 signature over package bytes is invalid or package was modified.")

    # 5. Verify global signature over (signature + trusted_comment)
    global_payload = sig_info["sig_bytes"] + sig_info["trusted_comment"].encode("utf-8")
    try:
        verifier_pubkey.verify(sig_info["global_sig"], global_payload)
    except InvalidSignature:
        raise ValueError("CRYPTOGRAPHIC VERIFICATION FAILED: Minisign global signature over trusted comment is invalid.")

    # 6. Verify signed version if announced_version is provided
    trusted_comment = sig_info["trusted_comment"]
    if announced_version:
        clean_ann = announced_version.lstrip("v")
        # Check if version is mentioned in trusted comment
        if clean_ann not in trusted_comment and announced_version not in trusted_comment:
            raise ValueError(
                f"Version mismatch: signature trusted comment ('{trusted_comment}') does not match announced version '{announced_version}'"
            )

    return {
        "status": "PASS",
        "key_id": key_id.hex().upper(),
        "trusted_comment": trusted_comment,
        "package_size": len(package_bytes)
    }

def main():
    parser = argparse.ArgumentParser(description="Cryptographic Tauri Updater Signature Verifier")
    parser.add_argument("--pubkey", help="Base64 public key or raw minisign public key text")
    parser.add_argument("--tauri-config", help="Path to tauri.conf.json to extract pubkey from")
    parser.add_argument("--package", required=True, help="Path to updater package file (.zip or .msi.zip)")
    parser.add_argument("--signature", help="Base64 signature string")
    parser.add_argument("--signature-file", help="Path to .sig file")
    parser.add_argument("--version", help="Announced release version")
    args = parser.parse_args()

    # Resolve Pubkey
    pubkey = args.pubkey
    if not pubkey and args.tauri_config:
        with open(args.tauri_config, "r", encoding="utf-8-sig") as f:
            cfg = json.load(f)
            pubkey = cfg.get("plugins", {}).get("updater", {}).get("pubkey")

    if not pubkey:
        print(json.dumps({"status": "FAIL", "error": "Public key not provided and could not be found in tauri-config"}))
        sys.exit(1)

    # Resolve Package Bytes
    if not os.path.exists(args.package):
        print(json.dumps({"status": "FAIL", "error": f"Package file '{args.package}' not found"}))
        sys.exit(1)
    with open(args.package, "rb") as f:
        pkg_bytes = f.read()

    # Resolve Signature
    signature = args.signature
    if not signature and args.signature_file:
        with open(args.signature_file, "r", encoding="utf-8-sig") as f:
            signature = f.read().strip()

    if not signature:
        print(json.dumps({"status": "FAIL", "error": "Signature string or signature file not provided"}))
        sys.exit(1)

    # Execute Cryptographic Verification
    try:
        res = verify_updater_signature(pubkey, pkg_bytes, signature, args.version)
        print(json.dumps(res, indent=2))
        sys.exit(0)
    except Exception as e:
        print(json.dumps({"status": "FAIL", "error": str(e)}, indent=2))
        sys.exit(1)

if __name__ == "__main__":
    main()
