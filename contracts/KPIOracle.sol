// SPDX-License-Identifier: MIT
pragma solidity ^0.8.21;

import {ECDSA} from "@openzeppelin/contracts/utils/cryptography/ECDSA.sol";

contract KPIOracle {
    address public signer;
    uint256 public epoch;
    uint256 public value; // 1e18 scale
    event Update(uint256 epoch, uint256 value);

    constructor(address _signer) {
        signer = _signer;
    }

    function update(uint256 _epoch, uint256 _value, bytes calldata sig) external {
        bytes32 digest = keccak256(abi.encode(block.chainid, address(this), _epoch, _value));
        address recoveredSigner = ECDSA.recover(ECDSA.toEthSignedMessageHash(digest), sig);
        require(recoveredSigner == signer, "Invalid signature");

        require(_epoch > epoch, "stale");
        epoch = _epoch;
        value = _value;
        emit Update(_epoch, _value);
    }
}
