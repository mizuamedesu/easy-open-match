// Copyright Epic Games, Inc. All Rights Reserved.

#include "easy_open_matchBPLibrary.h"
#include "easy_open_match.h"
#include "Async/Async.h"
#include "Async/TaskGraphInterfaces.h"

// Disable warnings for protobuf and gRPC headers
#pragma warning(push)
#pragma warning(disable: 4800) // Implicit conversion to bool
#pragma warning(disable: 4668) // Undefined preprocessor macro

#include "frontend.grpc.pb.h"
#include "messages.pb.h"

#include <grpcpp/grpcpp.h>
#include <memory>
#include <string>

#pragma warning(pop)

Ueasy_open_matchBPLibrary::Ueasy_open_matchBPLibrary(const FObjectInitializer& ObjectInitializer)
: Super(ObjectInitializer)
{
}

bool Ueasy_open_matchBPLibrary::TestgRPCCompilation()
{
	// This is a placeholder function to test if the plugin compiles
	UE_LOG(LogTemp, Log, TEXT("easy_open_match plugin is loaded and functional"));
	return true;
}

// ============================================================================
// UOpenMatchFindMatchAsyncAction Implementation
// ============================================================================

UOpenMatchFindMatchAsyncAction* UOpenMatchFindMatchAsyncAction::FindMatch(
	UObject* WorldContextObject,
	const FString& FrontendEndpoint,
	float TimeoutSeconds)
{
	UOpenMatchFindMatchAsyncAction* Action = NewObject<UOpenMatchFindMatchAsyncAction>();
	Action->WorldContext = WorldContextObject;
	Action->Endpoint = FrontendEndpoint;
	Action->Timeout = TimeoutSeconds;
	Action->RegisterWithGameInstance(WorldContextObject);
	return Action;
}

void UOpenMatchFindMatchAsyncAction::Activate()
{
	UE_LOG(LogTemp, Log, TEXT("OpenMatch: Starting matchmaking to endpoint: %s"), *Endpoint);

	// Execute matchmaking on a background thread
	Async(EAsyncExecution::TaskGraph, [this]()
	{
		ExecuteMatchmaking();
	});
}

void UOpenMatchFindMatchAsyncAction::ExecuteMatchmaking()
{
	UE_LOG(LogTemp, Log, TEXT("OpenMatch: Executing matchmaking..."));

	try
	{
		// Create gRPC channel
		std::shared_ptr<grpc::Channel> channel = grpc::CreateChannel(
			TCHAR_TO_UTF8(*Endpoint),
			grpc::InsecureChannelCredentials()
		);

		// Create Frontend service stub
		std::unique_ptr<openmatch::FrontendService::Stub> stub =
			openmatch::FrontendService::NewStub(channel);

		// ========================================
		// Step 1: CreateTicket
		// ========================================
		openmatch::CreateTicketRequest createRequest;
		openmatch::Ticket* ticket = createRequest.mutable_ticket();

		// Set up search fields with empty tags for simple matchmaking
		openmatch::SearchFields* searchFields = ticket->mutable_search_fields();
		searchFields->add_tags("");

		openmatch::Ticket createResponse;
		grpc::ClientContext createContext;

		UE_LOG(LogTemp, Log, TEXT("OpenMatch: Creating ticket..."));
		grpc::Status createStatus = stub->CreateTicket(&createContext, createRequest, &createResponse);

		if (!createStatus.ok())
		{
			FString ErrorMsg = FString::Printf(TEXT("CreateTicket failed: %s"),
				UTF8_TO_TCHAR(createStatus.error_message().c_str()));
			UE_LOG(LogTemp, Error, TEXT("%s"), *ErrorMsg);

			AsyncTask(ENamedThreads::GameThread_Local, [this, ErrorMsg]()
			{
				OnFailure.Broadcast(false, ErrorMsg);
				SetReadyToDestroy();
			});
			return;
		}

		FString TicketId = UTF8_TO_TCHAR(createResponse.id().c_str());
		UE_LOG(LogTemp, Log, TEXT("OpenMatch: Ticket created: %s"), *TicketId);

		// ========================================
		// Step 2: WatchAssignments
		// ========================================
		openmatch::WatchAssignmentsRequest watchRequest;
		watchRequest.set_ticket_id(TCHAR_TO_UTF8(*TicketId));

		grpc::ClientContext watchContext;
		// Set deadline for timeout
		std::chrono::system_clock::time_point deadline =
			std::chrono::system_clock::now() + std::chrono::seconds((int)Timeout);
		watchContext.set_deadline(deadline);

		UE_LOG(LogTemp, Log, TEXT("OpenMatch: Watching assignments (timeout: %.0f seconds)..."), Timeout);

		std::unique_ptr<grpc::ClientReader<openmatch::WatchAssignmentsResponse>> reader =
			stub->WatchAssignments(&watchContext, watchRequest);

		openmatch::WatchAssignmentsResponse watchResponse;
		FString ConnectionString;
		bool bFoundAssignment = false;

		while (reader->Read(&watchResponse))
		{
			if (watchResponse.has_assignment() &&
				!watchResponse.assignment().connection().empty())
			{
				ConnectionString = UTF8_TO_TCHAR(watchResponse.assignment().connection().c_str());
				bFoundAssignment = true;
				UE_LOG(LogTemp, Log, TEXT("OpenMatch: Assignment received: %s"), *ConnectionString);
				break;
			}
		}

		grpc::Status watchStatus = reader->Finish();

		// ========================================
		// Step 3: DeleteTicket (cleanup)
		// ========================================
		openmatch::DeleteTicketRequest deleteRequest;
		deleteRequest.set_ticket_id(TCHAR_TO_UTF8(*TicketId));

		google::protobuf::Empty deleteResponse;
		grpc::ClientContext deleteContext;

		UE_LOG(LogTemp, Log, TEXT("OpenMatch: Deleting ticket..."));
		grpc::Status deleteStatus = stub->DeleteTicket(&deleteContext, deleteRequest, &deleteResponse);

		if (!deleteStatus.ok())
		{
			UE_LOG(LogTemp, Warning, TEXT("OpenMatch: Failed to delete ticket: %s"),
				UTF8_TO_TCHAR(deleteStatus.error_message().c_str()));
		}

		// ========================================
		// Step 4: Report result
		// ========================================
		if (bFoundAssignment)
		{
			AsyncTask(ENamedThreads::GameThread_Local, [this, ConnectionString]()
			{
				OnSuccess.Broadcast(true, ConnectionString);
				SetReadyToDestroy();
			});
		}
		else if (watchStatus.error_code() == grpc::StatusCode::DEADLINE_EXCEEDED)
		{
			UE_LOG(LogTemp, Warning, TEXT("OpenMatch: Timeout waiting for assignment"));
			AsyncTask(ENamedThreads::GameThread_Local, [this]()
			{
				OnFailure.Broadcast(false, TEXT("Timeout waiting for match"));
				SetReadyToDestroy();
			});
		}
		else
		{
			FString ErrorMsg = FString::Printf(TEXT("WatchAssignments failed: %s"),
				UTF8_TO_TCHAR(watchStatus.error_message().c_str()));
			UE_LOG(LogTemp, Error, TEXT("%s"), *ErrorMsg);

			AsyncTask(ENamedThreads::GameThread_Local, [this, ErrorMsg]()
			{
				OnFailure.Broadcast(false, ErrorMsg);
				SetReadyToDestroy();
			});
		}
	}
	catch (const std::exception& e)
	{
		FString ErrorMsg = FString::Printf(TEXT("Exception: %s"), UTF8_TO_TCHAR(e.what()));
		UE_LOG(LogTemp, Error, TEXT("OpenMatch: %s"), *ErrorMsg);

		AsyncTask(ENamedThreads::GameThread_Local, [this, ErrorMsg]()
		{
			OnFailure.Broadcast(false, ErrorMsg);
			SetReadyToDestroy();
		});
	}
}
