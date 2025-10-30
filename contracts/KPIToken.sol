// SPDX-License-Identifier: MIT
pragma solidity ^0.8.21;

import "@openzeppelin/contracts/token/ERC20/ERC20.sol";
import "./interfaces/IKPIOracle.sol";

contract KPIToken is ERC20 {
    IKPIOracle public oracle;
    uint256 public lastValue;
    uint256 public lastEpoch;
    uint256 public alpha = 100; // basis points per unit gain
    address public emissions;   // emissions receiver (router/vault)

    constructor(string memory symbol, string memory name, address _oracle)
    ERC20(name, symbol) { oracle = IKPIOracle(_oracle); emissions = msg.sender; _mint(msg.sender, 1e18); }

    function sync() public {
        uint256 v = oracle.value();
        uint256 e = oracle.epoch();
        if (e > lastEpoch && v > lastValue) {
            uint256 delta = v - lastValue;
            uint256 mintAmt = (delta * alpha) / 100; // simple mapping
            _mint(emissions, mintAmt);
        }
        lastValue = v; lastEpoch = e;
    }
}
