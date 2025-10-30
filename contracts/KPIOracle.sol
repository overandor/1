// SPDX-License-Identifier: MIT
pragma solidity ^0.8.21;

contract KPIOracle {
    address public signer;
    uint256 public epoch;
    uint256 public value; // 1e18 scale
    event Update(uint256 epoch, uint256 value);

    constructor(address _signer){ signer=_signer; }

    function update(uint256 _epoch, uint256 _value, bytes calldata sig) external {
        bytes32 message = keccak256(abi.encodePacked(_epoch, _value));
        address recoveredSigner = recoverSigner(message, sig);
        require(recoveredSigner == signer, "Invalid signature");

        require(_epoch > epoch, "stale");
        epoch = _epoch; value = _value;
        emit Update(_epoch,_value);
    }

    function recoverSigner(bytes32 _message, bytes memory _signature)
        internal
        pure
        returns (address)
    {
        (bytes32 r, bytes32 s, uint8 v) = splitSignature(_signature);
        return ecrecover(_message, v, r, s);
    }

    function splitSignature(bytes memory sig)
        internal
        pure
        returns (
            bytes32 r,
            bytes32 s,
            uint8 v
        )
    {
        require(sig.length == 65, "invalid signature length");

        assembly {
            // first 32 bytes, after the length prefix
            r := mload(add(sig, 32))
            // next 32 bytes
            s := mload(add(sig, 64))
            // final byte (first byte of the next 32 bytes)
            v := byte(0, mload(add(sig, 96)))
        }

        return (r, s, v);
    }
}
