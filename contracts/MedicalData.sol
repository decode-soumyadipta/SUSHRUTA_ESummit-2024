// SPDX-License-Identifier: MIT
pragma solidity ^0.8.0;

contract MedicalData {
    struct Data {
        uint256 id;
        address patient;
        string prescriptionHash;
        string testResultsHash;
    }

    mapping(uint256 => Data) public medicalRecords;
    uint256 public recordCount;

    event MedicalDataStored(uint256 id, address indexed patient, string prescriptionHash, string testResultsHash);

    function storeMedicalData(string memory _prescriptionHash, string memory _testResultsHash) public {
        recordCount++;
        medicalRecords[recordCount] = Data(recordCount, msg.sender, _prescriptionHash, _testResultsHash);
        emit MedicalDataStored(recordCount, msg.sender, _prescriptionHash, _testResultsHash);
    }
}
