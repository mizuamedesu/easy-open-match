// Copyright Epic Games, Inc. All Rights Reserved.

#pragma once

#include "CoreMinimal.h"
#include "Kismet/BlueprintFunctionLibrary.h"
#include "Kismet/BlueprintAsyncActionBase.h"
#include "easy_open_matchBPLibrary.generated.h"

/**
 * Delegate for matchmaking completion
 */
DECLARE_DYNAMIC_MULTICAST_DELEGATE_TwoParams(FOnMatchmakingComplete, bool, bSuccess, FString, ConnectionString);

/**
 * Async Blueprint node for OpenMatch matchmaking
 */
UCLASS()
class UOpenMatchFindMatchAsyncAction : public UBlueprintAsyncActionBase
{
	GENERATED_BODY()

public:
	// Success delegate - called when match is found
	UPROPERTY(BlueprintAssignable)
	FOnMatchmakingComplete OnSuccess;

	// Failure delegate - called when matchmaking fails or times out
	UPROPERTY(BlueprintAssignable)
	FOnMatchmakingComplete OnFailure;

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
