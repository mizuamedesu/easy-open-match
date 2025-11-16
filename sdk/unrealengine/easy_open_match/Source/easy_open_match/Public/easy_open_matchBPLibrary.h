// Copyright Epic Games, Inc. All Rights Reserved.

#pragma once

#include "CoreMinimal.h"
#include "Kismet/BlueprintFunctionLibrary.h"
#include "Kismet/BlueprintAsyncActionBase.h"
#include "easy_open_matchBPLibrary.generated.h"

/**
 * Delegate for matchmaking success
 */
DECLARE_DYNAMIC_MULTICAST_DELEGATE_OneParam(FOnMatchmakingSuccess, FString, ConnectionString);

/**
 * Delegate for matchmaking failure
 */
DECLARE_DYNAMIC_MULTICAST_DELEGATE_OneParam(FOnMatchmakingFailure, FString, ErrorMessage);

/**
 * Delegate for matchmaking timeout
 */
DECLARE_DYNAMIC_MULTICAST_DELEGATE(FOnMatchmakingTimeout);

/**
 * Async Blueprint node for OpenMatch matchmaking
 */
UCLASS()
class UOpenMatchFindMatchAsyncAction : public UBlueprintAsyncActionBase
{
	GENERATED_BODY()

public:
	// Success delegate - called when match is found with connection string
	UPROPERTY(BlueprintAssignable)
	FOnMatchmakingSuccess OnSuccess;

	// Failure delegate - called when matchmaking fails with error message
	UPROPERTY(BlueprintAssignable)
	FOnMatchmakingFailure OnFailure;

	// Timeout delegate - called when matchmaking times out
	UPROPERTY(BlueprintAssignable)
	FOnMatchmakingTimeout OnTimeout;

	/**
	 * Find a match using OpenMatch Frontend service
	 * @param WorldContextObject - World context object
	 * @param FrontendEndpoint - gRPC endpoint (e.g., "localhost:50504")
	 * @param TimeoutSeconds - Timeout in seconds for waiting assignment (default: 60)
	 * @return Async action instance
	 */
	UFUNCTION(BlueprintCallable, meta = (BlueprintInternalUseOnly = "true", WorldContext = "WorldContextObject"), Category = "OpenMatch")
	static UOpenMatchFindMatchAsyncAction* FindMatch(
		UObject* WorldContextObject,
		const FString& FrontendEndpoint,
		float TimeoutSeconds = 60.0f
	);

	// UBlueprintAsyncActionBase interface
	virtual void Activate() override;

private:
	UPROPERTY()
	UObject* WorldContext;

	FString Endpoint;
	float Timeout;

	void ExecuteMatchmaking();
};

/**
 * Blueprint function library for OpenMatch
 */
UCLASS()
class Ueasy_open_matchBPLibrary : public UBlueprintFunctionLibrary
{
	GENERATED_UCLASS_BODY()

	/**
	 * Test function to check if gRPC can be compiled
	 */
	UFUNCTION(BlueprintCallable, Category = "OpenMatch")
	static bool TestgRPCCompilation();
};
