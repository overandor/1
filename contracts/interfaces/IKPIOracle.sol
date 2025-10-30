// SPDX-License-Identifier: MIT
pragma solidity ^0.8.21;

interface IKPIOracle {
    function epoch() external view returns (uint256);
    function value() external view returns (uint256);
}
